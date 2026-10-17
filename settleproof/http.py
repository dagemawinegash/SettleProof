import json
import time
import urllib.error
import urllib.request


class ServiceError(RuntimeError):
    def __init__(self, message, *, status=None, retry_after=None):
        super().__init__(message)
        self.status=status
        self.retry_after=retry_after


class Http:
    """Small HTTP client with bounded reads and secret-free error messages."""
    def __init__(self, base, headers):
        self.base = base.rstrip('/')
        self.headers = headers

    def request(self, method, path, body=None, *, raw=False, timeout=60, retries=0):
        for attempt in range(retries+1):
            try:
                result=self._request(method,path,body,raw=raw,timeout=timeout)
                self.last_retries=attempt
                return result
            except ServiceError as exc:
                if exc.status!=429 or attempt==retries:
                    raise
                delay=3*(attempt+1)
                try:
                    delay=min(20,max(delay,float(exc.retry_after)))
                except (ValueError,TypeError):
                    pass
                time.sleep(delay)

    def _request(self, method, path, body=None, *, raw=False, timeout=60):
        headers = dict(self.headers)
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        elif isinstance(body, bytes):
            headers['Content-Type'] = 'application/octet-stream'
        request = urllib.request.Request(self.base + path, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    raise ServiceError('Service response exceeds size limit')
        except urllib.error.HTTPError as exc:
            # Extract only diagnostic messages, never raw bodies, inputs, or headers.
            detail=''
            try:
                payload=json.loads(exc.read(4000))
                if isinstance(payload,dict):
                    fields=payload.get('detail')
                    if isinstance(fields,list):
                        detail='; '.join(str(v.get('msg','')) for v in fields if isinstance(v,dict))
                    if not detail:
                        nested=payload.get('data')
                        nested=nested if isinstance(nested,dict) else {}
                        message=payload.get('message') or payload.get('error') or nested.get('message') or nested.get('error')
                        if isinstance(message,dict):
                            message=message.get('message')
                        if isinstance(message,str):
                            detail=message
                for value in self.headers.values():
                    detail=detail.replace(value,'[REDACTED]').replace(value.removeprefix('Bearer '),'[REDACTED]')
                detail=detail[:500]
            except (ValueError,AttributeError):
                pass
            suffix=(': '+detail) if detail else ''
            raise ServiceError(f'{method} {path.split("?")[0]}: HTTP {exc.code}'+suffix,
                               status=exc.code,retry_after=exc.headers.get('Retry-After')) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ServiceError(f'{method} {path.split("?")[0]}: network failure or timeout') from None
        if raw:
            return data
        try:
            result = json.loads(data)
        except ValueError:
            raise ServiceError('Service returned invalid JSON') from None
        if not isinstance(result, dict):
            raise ServiceError('Service returned unexpected response shape')
        return result

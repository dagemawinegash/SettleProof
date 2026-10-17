import json

from .http import Http, ServiceError
from .prompt import SYSTEM


class River:
    def __init__(self, settings):
        self.http=Http(settings.river_base, {'Authorization':'Bearer '+settings.river_key})
        self.model=settings.model

    def models(self):
        return [item['id'] for item in self.http.request('GET','/models').get('data',[])]

    def generate(self, context, previous=None, feedback=None):
        messages=[{'role':'system','content':SYSTEM},
                  {'role':'user','content':json.dumps(context)}]
        if previous is not None:
            messages.extend([{'role':'assistant','content':json.dumps({'code':previous})},
                             {'role':'user','content':json.dumps({'checked_failure':feedback,
                              'request':'Repair the program and return the full code in the required JSON object.'})}])
        payload=self.http.request('POST','/chat/completions',{
            'model':self.model,'messages':messages,'max_tokens':12000,
            'reasoning_effort':'high','response_format':{'type':'json_object'}},timeout=240,retries=2)
        choices=payload.get('choices',[])
        if not choices or choices[0].get('finish_reason')!='stop':
            raise ServiceError('Model did not complete a response within the output budget')
        try:
            content=json.loads(choices[0]['message']['content'])
            code=content['code']
            if set(content)!={'code'} or not isinstance(code,str) or not code.strip() or len(code.encode())>64000:
                raise ValueError()
        except (ValueError,KeyError,TypeError):
            raise ServiceError('Model returned an invalid code response') from None
        return code, {'id':payload.get('id'),'model':payload.get('model',self.model),
                      'rate_limit_retries':getattr(self.http,'last_retries',0),
                      'usage':payload.get('usage',{}),'finish_reason':choices[0].get('finish_reason')}

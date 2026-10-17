class Metadata:
    """Persist metadata only: original rows, generated source, and secrets stay local."""
    def __init__(self, url):
        self.url=url

    def save(self, manifest):
        if not self.url:
            raise ValueError('Missing database configuration; pull Stripe Projects environment first')
        import psycopg
        from psycopg.types.json import Jsonb
        # Do not return driver messages, which can include a credential-bearing DSN.
        try:
            with psycopg.connect(self.url,connect_timeout=10,sslmode='require') as connection:
                connection.execute('''CREATE TABLE IF NOT EXISTS settleproof_runs (
                    run_id text PRIMARY KEY, started_at text NOT NULL,
                    status text NOT NULL, metadata jsonb NOT NULL)''')
                connection.execute('''INSERT INTO settleproof_runs(run_id,started_at,status,metadata)
                    VALUES (%s,%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET
                    status=excluded.status, metadata=excluded.metadata''',
                    (manifest['run_id'],manifest['started_at'],manifest['status'],Jsonb(manifest)))
        except psycopg.Error:
            raise RuntimeError('Run metadata database could not be reached or written') from None

    def verify(self, run_id):
        import psycopg
        try:
            with psycopg.connect(self.url,connect_timeout=10,sslmode='require') as connection:
                result=connection.execute('SELECT metadata FROM settleproof_runs WHERE run_id=%s',(run_id,)).fetchone()
                return result[0] if result else None
        except psycopg.Error:
            raise RuntimeError('Run metadata read-back failed') from None

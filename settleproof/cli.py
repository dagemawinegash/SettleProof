import argparse
import json
from pathlib import Path
import sys

from .agent import Agent
from .checker import check
from .config import Settings
from .createos import CreateOS
from .inputs import Inputs
from .metadata import Metadata
from .river import River
from .replay import replay_saved


def main():
    parser=argparse.ArgumentParser(description='SettleProof: remote coding agent and independent CSV checker')
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('doctor',help='Verify model, sandbox identity, and database access; never display secrets')
    serve=sub.add_parser('serve',help='Start the local browser application')
    serve.add_argument('--port',type=int,default=8000)
    run=sub.add_parser('run',help='Generate Python, execute in CreateOS, independently check, and replay')
    run.add_argument('payments',type=Path)
    run.add_argument('bank',type=Path)
    run.add_argument('--output',type=Path,default=Path('artifacts'))
    run.add_argument('--max-attempts',type=int,default=3)
    replay=sub.add_parser('replay',help='Rerun a saved accepted program in a new CreateOS sandbox; no model call')
    replay.add_argument('run_directory',type=Path)
    verify=sub.add_parser('check',help='Independently check a candidate JSON against original input files; no API calls')
    verify.add_argument('payments',type=Path)
    verify.add_argument('bank',type=Path)
    verify.add_argument('candidate',type=Path)
    args=parser.parse_args()
    try:
        if args.command=='serve':
            import uvicorn
            from .server import create_app
            uvicorn.run(create_app(),host='127.0.0.1',port=args.port,access_log=False)
            return 0
        if args.command=='check':
            inputs=Inputs.load(args.payments,args.bank)
            report=check(json.loads(args.candidate.read_text(encoding='utf-8')),inputs)
            print(json.dumps(report,indent=2))
            return 0
        settings=Settings.load()
        if args.command=='replay':
            path,result=replay_saved(settings,args.run_directory)
            print(json.dumps({'status':result['status'],'model_called':False,'evidence':str(path),
                              'sandbox_cleanup':result.get('sandbox_cleanup')},indent=2))
            return 0 if result['status']=='checked' and result.get('sandbox_cleanup')=='deleted' else 1
        if args.command=='doctor':
            models=River(settings).models()
            identity=CreateOS(settings).identity()
            metadata=Metadata(settings.database_url)
            probe={'run_id':'doctor','started_at':'diagnostic','status':'diagnostic'}
            metadata.save(probe)
            verified=metadata.verify('doctor')==probe
            print(json.dumps({'available_models':models,'selected_model':settings.model,
                'selected_model_available':settings.model in models,'createos_stats':identity.get('stats'),
                'database_write_read_verified':verified},indent=2))
            return 0 if verified and settings.model in models else 1
        folder,manifest=Agent(settings).run(args.payments,args.bank,output=args.output,max_attempts=args.max_attempts)
        print(json.dumps({'run_id':manifest['run_id'],'status':manifest['status'],'artifacts':str(folder),
                          'replay_verified':manifest['replay_verified'],
                          'metadata_persisted':manifest['metadata_persisted']},indent=2))
        return 0 if manifest['status']=='checked' and manifest['metadata_persisted'] and manifest.get('sandbox_cleanup')=='deleted' else 1
    except (KeyboardInterrupt, SystemExit):
        raise
    except Exception as exc:
        # Safe messages only; raw HTTP/driver exceptions can expose connection details.
        safe=isinstance(exc,(ValueError,RuntimeError))
        print('SettleProof: '+(str(exc) if safe else type(exc).__name__+'; inspect local run evidence'),file=sys.stderr)
        return 1


if __name__=='__main__':
    raise SystemExit(main())

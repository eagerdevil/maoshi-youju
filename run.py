from pathlib import Path
import argparse, sys, webbrowser
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'.vendor'))
sys.path.insert(0,str(ROOT))
if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--open',action='store_true'); args=parser.parse_args()
    import uvicorn
    if args.open:
        import threading
        threading.Timer(1.5,lambda:webbrowser.open(f'http://127.0.0.1:{args.port}')).start()
    uvicorn.run('backend.app:app',host='127.0.0.1',port=args.port)

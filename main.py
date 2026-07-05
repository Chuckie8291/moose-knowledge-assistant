import sys, os, traceback

# Ensure backend/ is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

print("Starting Moose Knowledge Assistant...", flush=True)
print(f"Python: {sys.version}", flush=True)
print(f"CWD: {os.getcwd()}", flush=True)
print(f"Files in CWD: {os.listdir('.')[:10]}", flush=True)

try:
    from app.main import app
    print(f"App loaded: {app.title}", flush=True)
except Exception:
    traceback.print_exc()
    # Create a minimal fallback app so Railway doesn't kill the process
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse
    app = FastAPI()

    @app.get("/")
    async def root():
        return JSONResponse({"error": "App failed to start", "traceback": traceback.format_exc()})

    @app.get("/health")
    async def health():
        return {"status": "starting", "error": str(sys.exc_info()[1])}

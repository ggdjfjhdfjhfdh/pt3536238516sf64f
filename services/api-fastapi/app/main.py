import os
import redis
import json
import asyncio
import stripe
from rq import Queue

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import StreamingResponse

app = FastAPI()

# CORS – dominios permitidos
allowed_origins = [
    "https://www.auditatetumismo.es",
    "https://trae-pentest-express-landing-9olk.vercel.app",
    "https://pentest-express-landing.vercel.app",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5500"
]

# Añadir dominios de variables de entorno si existen
success_url = os.getenv("SUCCESS_URL")
cancel_url = os.getenv("CANCEL_URL")
if success_url:
    from urllib.parse import urlparse
    parsed = urlparse(success_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in allowed_origins:
        allowed_origins.append(origin)
if cancel_url:
    from urllib.parse import urlparse
    parsed = urlparse(cancel_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    if origin not in allowed_origins:
        allowed_origins.append(origin)

print(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
    allow_credentials=True,
)

# ---------- Stripe ----------
stripe.api_key = os.getenv("STRIPE_SECRET")
PRICE_ID       = os.getenv("STRIPE_PRICE_ID")
WHSEC          = os.getenv("STRIPE_WEBHOOK_SECRET")

# ---------- Cola Redis / RQ ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://red-d20a0bvgi27c73cbmk3g:6379")
rds = redis.from_url(REDIS_URL)
q = Queue('scan_queue', connection=rds)

# ---------- Endpoints ----------
@app.get("/scan/{job_id}/status")
def scan_status(job_id: str):
    meta = rds.hget("rq:job:"+job_id, "meta")
    return json.loads(meta)["progress"] if meta else {"state":"unknown"}

@app.get("/scan/{job_id}/events")
async def scan_events(job_id: str):
    async def event_stream():
        last_state = None
        while True:
            try:
                meta = rds.hget("rq:job:"+job_id, "meta")
                if meta:
                    progress_data = json.loads(meta)["progress"]
                    yield f"data: {json.dumps(progress_data)}\n\n"
                    
                    # Si el estado cambió a completed o failed, terminar el stream
                    current_state = progress_data.get("state")
                    if current_state in ["completed", "failed"] and current_state != last_state:
                        break
                    last_state = current_state
                else:
                    # Si no hay metadata, enviar estado desconocido
                    yield f"data: {{\"state\": \"unknown\"}}\n\n"
                
                await asyncio.sleep(3)
            except Exception as e:
                print(f"Error in SSE stream: {e}")
                yield f"data: {{\"state\": \"failed\", \"error\": \"Stream error\"}}\n\n"
                break

    return StreamingResponse(event_stream(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Cache-Control"
    })


@app.post("/stripe/create-checkout")
async def create_checkout():
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": PRICE_ID, "quantity": 1}],
        custom_fields=[{
            "key": "domain",
            "label": {"type": "custom", "custom": "Dominio a escanear"},
            "type": "text",
            "text": { "minimum_length": 3, "maximum_length": 64 }
        }],
        success_url=os.getenv("SUCCESS_URL"),
        cancel_url =os.getenv("CANCEL_URL")
    )
    return {"id": session.id}



@app.post("/stripe/webhook")
async def stripe_webhook(req: Request):
    payload = await req.body()
    sig     = req.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, sig, WHSEC)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Bad signature")

    if event["type"] == "checkout.session.completed":
        data    = event["data"]["object"]
        dominio = data["custom_fields"][0]["text"]["value"]

        email   = data["customer_details"]["email"]

        # ► Encolar trabajo RQ
        q.enqueue('pentest.core._run_scan_job', dominio, email)
        print(f"Published scan for {dominio} → {email}")

    return {"ok": True}


@app.get("/debug/redis-jobs")
async def debug_redis_jobs():
    """Endpoint de debug para ver todos los trabajos en Redis."""
    try:
        job_keys = rds.keys("rq:job:*")
        jobs_info = []
        
        for key in job_keys[:10]:  # Limitar a 10 para evitar sobrecarga
            try:
                job_data_raw = rds.hget(key, "data")
                if job_data_raw:
                    job_data = json.loads(job_data_raw)
                    jobs_info.append({
                        "job_id": key.decode('utf-8').replace('rq:job:', ''),
                        "args": job_data.get('args', []),
                        "created_at": job_data.get('created_at'),
                        "status": job_data.get('status')
                    })
            except Exception as e:
                jobs_info.append({
                    "job_id": key.decode('utf-8').replace('rq:job:', ''),
                    "error": str(e)
                })
        
        return {
            "total_jobs": len(job_keys),
            "jobs_sample": jobs_info
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/stripe/session/{session_id}")
async def get_stripe_session(session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Buscar el job_id asociado con el email del cliente
        customer_email = session.customer_details.email if session.customer_details else None
        job_id = None
        
        print(f"Searching for jobs with email: {customer_email}")
        
        if customer_email:
            # Buscar en todas las claves de Redis que contengan jobs
            try:
                # Buscar todas las claves de jobs en Redis
                job_keys = rds.keys("rq:job:*")
                print(f"Found {len(job_keys)} job keys in Redis")
                
                for key in job_keys:
                    try:
                        # Obtener los datos del job
                        job_data_raw = rds.hget(key, "data")
                        if job_data_raw:
                            job_data = json.loads(job_data_raw)
                            args = job_data.get('args', [])
                            
                            # Verificar si el segundo argumento (email) coincide
                            if len(args) >= 2 and args[1] == customer_email:
                                # Extraer el job_id del nombre de la clave
                                job_id = key.decode('utf-8').replace('rq:job:', '')
                                print(f"Found matching job: {job_id} for email: {customer_email}")
                                break
                    except Exception as e:
                        print(f"Error processing job key {key}: {e}")
                        continue
                        
                if not job_id:
                    print(f"No job found for email: {customer_email}")
                    
            except Exception as e:
                print(f"Error searching for jobs: {e}")
        
        result = {
            "status": session.status, 
            "customer_email": customer_email,
            "job_id": job_id
        }
        print(f"Returning session data: {result}")
        return result
        
    except Exception as e:
        print(f"Error in get_stripe_session: {e}")
        raise HTTPException(status_code=400, detail=str(e))

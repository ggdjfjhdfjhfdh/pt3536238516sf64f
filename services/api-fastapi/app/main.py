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

# CORS – tu dominio de Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://www.auditatetumismo.es"],
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


@app.get("/stripe/session/{session_id}")
async def get_stripe_session(session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        
        # Buscar el job_id asociado con el email del cliente
        customer_email = session.customer_details.email if session.customer_details else None
        job_id = None
        
        if customer_email:
            # Buscar trabajos en la cola que coincidan con el email
            # Esto es una aproximación, en producción sería mejor tener un mapeo directo
            jobs = q.get_jobs()
            for job in jobs:
                if hasattr(job, 'args') and len(job.args) >= 2 and job.args[1] == customer_email:
                    job_id = job.id
                    break
            
            # Si no se encuentra en trabajos activos, buscar en trabajos completados/fallidos
            if not job_id:
                from rq import get_current_job
                from rq.registry import StartedJobRegistry, FinishedJobRegistry, FailedJobRegistry
                
                registries = [
                    StartedJobRegistry(queue=q),
                    FinishedJobRegistry(queue=q),
                    FailedJobRegistry(queue=q)
                ]
                
                for registry in registries:
                    for job_id_candidate in registry.get_job_ids():
                        try:
                            job = q.connection.hget(f"rq:job:{job_id_candidate}", "data")
                            if job:
                                job_data = json.loads(job)
                                if len(job_data.get('args', [])) >= 2 and job_data['args'][1] == customer_email:
                                    job_id = job_id_candidate
                                    break
                        except:
                            continue
                    if job_id:
                        break
        
        return {
            "status": session.status, 
            "customer_email": customer_email,
            "job_id": job_id
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

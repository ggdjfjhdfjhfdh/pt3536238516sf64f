import os
import redis
import json
import asyncio
import stripe

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

# ---------- Endpoints ----------
@app.get("/scan/{job_id}/status")
def scan_status(job_id: str):
    meta = rds.hget("rq:job:"+job_id, "meta")
    return json.loads(meta)["progress"] if meta else {"state":"unknown"}

@app.get("/scan/{job_id}/events")
async def scan_events(job_id: str):
    async def event_stream():
        while True:
            meta = rds.hget("rq:job:"+job_id, "meta")
            if meta:
                progress_data = json.loads(meta)["progress"]
                yield f"data: {json.dumps(progress_data)}\n\n"
            await asyncio.sleep(3) # Simulate delay

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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

        # ► Publicar en la cola BLPOP
        rds.rpush("scan_queue", json.dumps({"domain": dominio, "email": email}))
        print(f"Published scan for {dominio} → {email}")

    return {"ok": True}


@app.get("/stripe/session/{session_id}")
async def get_stripe_session(session_id: str):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {"status": session.status, "customer_email": session.customer_details.email}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

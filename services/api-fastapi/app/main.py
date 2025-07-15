import os, stripe, redis, rq
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS – tu dominio de Vercel
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://pt-ldn-61169603-jpga.vercel.app/"],
    allow_methods=["POST"],
    allow_headers=["*"],
)

# ---------- Stripe ----------
stripe.api_key = os.getenv("STRIPE_SECRET")
PRICE_ID       = os.getenv("STRIPE_PRICE_ID")
WHSEC          = os.getenv("STRIPE_WEBHOOK_SECRET")

# ---------- Cola Redis / RQ ----------
REDIS_URL = os.getenv("REDIS_URL", "redis://red-d1r7117diees73flo1lg:6379")
scan_q    = rq.Queue("scans", connection=redis.from_url(REDIS_URL))

# ---------- Endpoints ----------
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

        # ► Encola el trabajo: módulo run_scan.generate_pdf
        scan_q.enqueue("run_scan.generate_pdf", dominio, email)
        print(f"Enqueued scan for {dominio} → {email}")

    return {"ok": True}

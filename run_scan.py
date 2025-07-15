import os
import redis
from rq import Queue, Worker
from reportlab.pdfgen import canvas

REDIS_URL = os.getenv("REDIS_URL", "redis://red-d1r7117diees73flo1lg:6379")
q = Queue("scans", connection=redis.from_url(REDIS_URL))

def generate_pdf(domain, email):
    path = f"/tmp/{domain}.pdf"
    c = canvas.Canvas(path)
    c.drawString(100, 750, f"Informe de seguridad para {domain}")
    c.save()
    print("PDF listo:", path)

if __name__ == "__main__":
    Worker([q]).work()

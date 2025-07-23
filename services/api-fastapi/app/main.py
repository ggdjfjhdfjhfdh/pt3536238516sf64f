from fastapi import FastAPI
from rq import Queue
from rq.connections import Connection
from redis import Redis

app = FastAPI()

# Asumo que tienes una conexión a Redis configurada.
# Si no es así, necesitarás ajustar esta parte.
redis_conn = Redis.from_url('redis://default:tu_contraseña_de_redis@tu_host_de_redis:tu_puerto_de_redis')
q = Queue(connection=redis_conn)

@app.get("/")
def read_root():
    return {"Hello": "World"}

# Aquí deberías añadir el resto de tu lógica de la aplicación.
# Por ejemplo, las rutas que encolan trabajos en RQ.
"""AWS Lambda entrypoint (REST API Gateway -> Mangum -> the SAME FastAPI app used on EC2)."""

from mangum import Mangum

from app.api.main import app

handler = Mangum(app, lifespan="off")

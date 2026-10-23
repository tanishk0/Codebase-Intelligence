from fastapi import FastAPI
from app.api.routes.repositories import router as repositories_router

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status" : "ok"}


app.include_router(repositories_router)




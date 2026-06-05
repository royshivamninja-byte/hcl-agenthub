from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.agents.orchestrator import orchestrate

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Request(BaseModel):
    message: str

@app.post("/chat")
def chat(req: Request):
    message = req.message.strip()
    if not message:
        return {
            "workflow": [{
                "agent": "Orchestrator",
                "task": "Please enter a question or request."
            }]
        }

    result = orchestrate(message)

    return {
        "workflow": result
    }

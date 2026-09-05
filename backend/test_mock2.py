import sys
sys.path.insert(0, r'C:\Users\DELL\OneDrive\Desktop\shreeka\AI Workflow Simulation Engine\backend')

from app.services.ai.ai_service import MockAIService
from app.schemas.review import AIReviewResponse
import asyncio

async def test():
    service = MockAIService()
    for i in range(10):
        raw = await service.generate_json(prompt='test', system_prompt='test')
        print(f'Attempt {i}: severity={raw.get("severity")}')
        
        try:
            validated = AIReviewResponse.model_validate(raw)
            print(f'  Validated: severity={validated.severity}')
        except Exception as e:
            print(f'  Validation error: {e}')

asyncio.run(test())
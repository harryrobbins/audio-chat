import json
import uuid
import asyncio
from google.adk import Runner
from google.adk.agents import SequentialAgent, LoopAgent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from .fact_extractor.agent import fact_extractor
from .persona_generator.agent import persona_generator
from .script_writer.agent import script_writer
from .script_critic.agent import script_critic
from sqlalchemy.ext.asyncio import AsyncSession
import models
from typing import AsyncGenerator

class PodcastFlow:
    def __init__(self):
        self.app_name = "podcast_app"
        self.session_service = InMemorySessionService()
        
        # Define agents
        self.fact_extractor = fact_extractor
        self.persona_generator = persona_generator
        self.script_writer = script_writer
        self.script_critic = script_critic

        # Iterative Loop: Writer -> Critic
        self.refinement_loop = LoopAgent(
            name="refinement_loop",
            sub_agents=[
                SequentialAgent(
                    name="writer_critic_sequence",
                    sub_agents=[self.script_writer, self.script_critic]
                )
            ],
            max_iterations=3
        )

        # Full Generation Flow: Persona Generator -> Refinement Loop
        self.generation_workflow = SequentialAgent(
            name="podcast_generation_workflow",
            sub_agents=[self.persona_generator, self.refinement_loop]
        )

    async def _get_runner(self, agent) -> Runner:
        return Runner(
            app_name=self.app_name,
            agent=agent,
            session_service=self.session_service
        )

    async def build_knowledge_base(self, project_id: int, db: AsyncSession) -> AsyncGenerator[dict, None]:
        # Get all documents for the project
        from sqlalchemy import select
        result = await db.execute(select(models.Document).where(models.Document.project_id == project_id))
        docs = result.scalars().all()
        
        yield {"status": "Starting knowledge base build", "total_docs": len(docs)}
        await asyncio.sleep(0.05)
        
        for i, doc in enumerate(docs):
            yield {"status": f"Analyzing document {i+1}/{len(docs)}: {doc.title}", "doc_id": doc.id}
            await asyncio.sleep(0.05)
            
            try:
                facts_data = await self.extract_facts(doc.content)
                
                # Save facts to DB
                for fact_item in facts_data.get("key_facts", []):
                    db_fact = models.Fact(
                        project_id=project_id,
                        document_id=doc.id,
                        point=fact_item["point"],
                        context=fact_item["context"]
                    )
                    db.add(db_fact)
                
                await db.commit()
                yield {"status": f"Extracted {len(facts_data.get('key_facts', []))} facts from {doc.title}"}
                await asyncio.sleep(0.05)
            except Exception as e:
                yield {"status": f"Error analyzing {doc.title}: {str(e)}", "error": True}
                await asyncio.sleep(0.05)

        yield {"status": "Knowledge base build complete", "done": True}
        await asyncio.sleep(0.05)

    async def extract_facts(self, text: str) -> dict:
        user_id = "default_user"
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        runner = await self._get_runner(self.fact_extractor)
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=f"Extract facts from this text:\n\n{text}")]
        )
        
        events = [event async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message)]
        if not events:
            raise Exception(
                "Fact extractor agent returned no events. This usually indicates an API key or network error. "
                "Please verify that your GEMINI_API_KEY in the .env file is set to a valid Google Gemini API Key."
            )
        final_text = self._get_text_from_event(events[-1])
        return self._parse_json(final_text)

    async def generate_script_stream(self, project_id: int, prompt: str, db: AsyncSession, max_loops: int = 3) -> AsyncGenerator[dict, None]:
        yield {"status": "Gathering facts from knowledge base..."}
        await asyncio.sleep(0.05)
        
        # Get all facts for the project
        from sqlalchemy import select
        result = await db.execute(select(models.Fact).where(models.Fact.project_id == project_id))
        facts_list = result.scalars().all()
        
        facts = {
            "summary": f"Knowledge base for project {project_id}",
            "key_facts": [{"point": f.point, "context": f.context} for f in facts_list]
        }
        
        facts_str = json.dumps(facts, indent=2)
        
        yield {"status": "Initializing agent workflow..."}
        await asyncio.sleep(0.05)
        
        self.refinement_loop.max_iterations = max_loops
        
        user_id = "default_user"
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        runner = await self._get_runner(self.generation_workflow)
        
        # Combine facts and the user's guiding prompt
        full_prompt = f"""
        GUIDING PROMPT: {prompt}
        
        FACTS TO USE:
        {facts_str}
        
        Generate a conversational script based on these facts, following the guiding prompt.
        IMPORTANT: Use ONLY spoken words. NO stage directions, NO music cues, NO sound effects.
        """
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=full_prompt)]
        )
        
        yield {"status": "Agents are collaborating on the script..."}
        await asyncio.sleep(0.05)
        
        # We run the workflow and listen to events
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message):
            if event.author == "persona_generator":
                yield {"status": "Generated personas", "personas": True}
                await asyncio.sleep(0.05)
            elif event.author == "script_writer":
                yield {"status": "Script writer is drafting/refining...", "step": "writing"}
                await asyncio.sleep(0.05)
            elif event.author == "script_critic":
                yield {"status": "Script critic is reviewing...", "step": "critique"}
                await asyncio.sleep(0.05)

        # Extract final result
        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        history = session.events
        personas = None
        final_script = None
        
        for event in history:
            event_text = self._get_text_from_event(event)
            if not event_text: continue
            if event.author == "persona_generator":
                try:
                    parsed = self._parse_json(event_text)
                    if "personas" in parsed: personas = parsed
                except: pass
            elif event.author == "script_writer":
                try:
                    parsed = self._parse_json(event_text)
                    if "lines" in parsed: final_script = parsed
                except: pass
        
        if final_script:
            # Save script and personas to DB
            db_script = models.Script(
                project_id=project_id,
                title=final_script.get("title", "Untitled Podcast"),
                content={
                    "script": final_script,
                    "personas": personas
                },
                prompt=prompt
            )
            db.add(db_script)
            await db.commit()
            await db.refresh(db_script)
            
            yield {"status": "Script finalized and saved", "script_id": db_script.id, "done": True, "result": final_script, "personas": personas}
            await asyncio.sleep(0.05)
        else:
            yield {"status": "Failed to generate script", "error": True}
            await asyncio.sleep(0.05)

    async def generate_script(self, facts: dict, max_loops: int = 3) -> dict:
        self.refinement_loop.max_iterations = max_loops
        
        user_id = "default_user"
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        runner = await self._get_runner(self.generation_workflow)
        facts_str = json.dumps(facts, indent=2)
        
        full_prompt = f"""
        FACTS TO USE:
        {facts_str}
        
        Generate a conversational script based on these facts.
        IMPORTANT: Use ONLY spoken words. NO stage directions, NO music cues, NO sound effects.
        """
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=full_prompt)]
        )
        
        # Run the agent workflow
        events = [event async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message)]
        
        # Extract personas and script from session history
        session = await self.session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        history = session.events
        personas = None
        final_script = None
        
        for event in history:
            event_text = self._get_text_from_event(event)
            if not event_text: continue
            if event.author == "persona_generator":
                try:
                    parsed = self._parse_json(event_text)
                    if "personas" in parsed: personas = parsed
                except: pass
            elif event.author == "script_writer":
                try:
                    parsed = self._parse_json(event_text)
                    if "lines" in parsed: final_script = parsed
                except: pass
                
        if not personas or not final_script:
            raise Exception("Failed to generate personas or script in the workflow.")
            
        return {
            "personas": personas,
            "script": final_script
        }

    def _get_text_from_event(self, event) -> str:
        if event.content and event.content.parts:
            return "".join([p.text for p in event.content.parts if p.text])
        return ""

    def _parse_json(self, text: str) -> dict:
        cleaned = text.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            parts = cleaned.split("```")
            if len(parts) >= 3:
                cleaned = parts[1].strip()
        return json.loads(cleaned)

# Expose a global singleton instance of the workflow to prevent multiple instantiations of the ADK agents
flow = PodcastFlow()

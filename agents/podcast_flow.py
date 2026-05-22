import json
import uuid
import asyncio
from google.adk import Runner
from google.adk.agents import SequentialAgent, LoopAgent
from google.adk.sessions import InMemorySessionService
from google.genai import types
from .fact_extractor.agent import fact_extractor
from .fact_reconciler.agent import fact_reconciler
from .fact_curator.agent import fact_curator
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
        self.fact_reconciler = fact_reconciler
        self.fact_curator = fact_curator
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

    async def reconcile_facts_agent(self, existing_facts: list, new_facts: list) -> dict:
        user_id = "default_user"
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        runner = await self._get_runner(self.fact_reconciler)
        
        # Format existing and new facts in a readable JSON block
        prompt_content = f"""
        EXISTING compiled facts:
        {json.dumps(existing_facts, indent=2)}
        
        NEW candidate facts to merge:
        {json.dumps(new_facts, indent=2)}
        """
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=prompt_content)]
        )
        
        events = [event async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message)]
        if not events:
            raise Exception("Fact reconciler agent returned no events.")
        final_text = self._get_text_from_event(events[-1])
        return self._parse_json(final_text)

    async def curate_facts_agent(self, compiled_facts: list) -> dict:
        user_id = "default_user"
        session_id = str(uuid.uuid4())
        await self.session_service.create_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id
        )
        
        runner = await self._get_runner(self.fact_curator)
        
        prompt_content = f"""
        COMPILED facts to curate:
        {json.dumps(compiled_facts, indent=2)}
        """
        
        new_message = types.Content(
            role="user",
            parts=[types.Part(text=prompt_content)]
        )
        
        events = [event async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=new_message)]
        if not events:
            raise Exception("Fact curator agent returned no events.")
        final_text = self._get_text_from_event(events[-1])
        return self._parse_json(final_text)

    async def build_knowledge_base(self, project_id: int, db: AsyncSession) -> AsyncGenerator[dict, None]:
        # 1. Get all documents for the project
        from sqlalchemy import select, delete
        result = await db.execute(select(models.Document).where(models.Document.project_id == project_id))
        docs = result.scalars().all()
        
        if not docs:
            yield {"status": "No source documents found. Add documents first.", "done": True}
            await asyncio.sleep(0.05)
            return

        # Clear existing facts to compile fresh
        yield {"status": "Clearing existing knowledge base facts...", "total_docs": len(docs)}
        await asyncio.sleep(0.05)
        await db.execute(delete(models.Fact).where(models.Fact.project_id == project_id))
        await db.commit()

        # 2. Extract facts in PARALLEL using GEMINI_LITE_MODEL
        yield {"status": f"Phase 1: Starting parallel fact extraction on all {len(docs)} documents..."}
        await asyncio.sleep(0.05)
        
        tasks = []
        for doc in docs:
            tasks.append(self.extract_facts(doc.content))
            
        try:
            # Gather all extraction results in parallel
            extractions = await asyncio.gather(*tasks)
            yield {"status": f"Phase 1 complete: Extracted raw facts from all {len(docs)} documents."}
            await asyncio.sleep(0.05)
        except Exception as e:
            yield {"status": f"Error during parallel fact extraction: {str(e)}", "error": True}
            await asyncio.sleep(0.05)
            return

        # 3. Reconcile facts SEQUENTIALLY using GEMINI_MODEL
        yield {"status": "Phase 2: Reconciling facts sequentially..."}
        await asyncio.sleep(0.05)
        
        compiled_facts = [] # will store list of dicts: {"point": "...", "context": "...", "document_ids": [doc_id1, ...]}
        
        for idx, (doc, facts_data) in enumerate(zip(docs, extractions)):
            new_candidate_facts = facts_data.get("key_facts", [])
            yield {"status": f"Integrating {len(new_candidate_facts)} facts from document {idx+1}/{len(docs)}: {doc.title}..."}
            await asyncio.sleep(0.05)
            
            if not new_candidate_facts:
                continue
                
            if not compiled_facts:
                # First document: just initialize the compiled facts
                for fact_item in new_candidate_facts:
                    compiled_facts.append({
                        "point": fact_item["point"],
                        "context": fact_item["context"],
                        "document_ids": [doc.id]
                    })
            else:
                # Subsequent documents: call reconciler agent
                try:
                    # Provide compiled facts with temporary 0-based indices as IDs
                    existing_facts_with_ids = [
                        {"id": i, "point": f["point"], "context": f["context"]}
                        for i, f in enumerate(compiled_facts)
                    ]
                    
                    reconciliation_result = await self.reconcile_facts_agent(
                        existing_facts=existing_facts_with_ids,
                        new_facts=new_candidate_facts
                    )
                    
                    # Apply reconciliation decisions
                    reconciled_list = reconciliation_result.get("reconciled_facts", [])
                    new_compiled_facts = []
                    
                    for item in reconciled_list:
                        ext_id = item.get("existing_fact_id")
                        if ext_id is not None and 0 <= ext_id < len(compiled_facts):
                            # Extended fact: update it and add current doc ID to its references
                            existing_fact = compiled_facts[ext_id]
                            existing_fact["point"] = item["point"]
                            existing_fact["context"] = item["context"]
                            if doc.id not in existing_fact["document_ids"]:
                                existing_fact["document_ids"].append(doc.id)
                        else:
                            # Brand-new fact
                            new_compiled_facts.append({
                                "point": item["point"],
                                "context": item["context"],
                                "document_ids": [doc.id]
                            })
                            
                    # Append the new facts to the compiled list
                    compiled_facts.extend(new_compiled_facts)
                    
                except Exception as e:
                    yield {"status": f"Warning: Reconciler error on {doc.title}: {str(e)}. Appending facts directly.", "warning": True}
                    await asyncio.sleep(0.05)
                    # Fallback: append them directly
                    for fact_item in new_candidate_facts:
                        compiled_facts.append({
                            "point": fact_item["point"],
                            "context": fact_item["context"],
                            "document_ids": [doc.id]
                        })

        # 4. Perform final global curation using GEMINI_MODEL
        yield {"status": "Phase 3: Performing final knowledge base curation and synthesis..."}
        await asyncio.sleep(0.05)
        
        final_facts = []
        if compiled_facts:
            try:
                curation_result = await self.curate_facts_agent(compiled_facts)
                curated_list = curation_result.get("curated_facts", [])
                for cf in curated_list:
                    final_facts.append({
                        "point": cf["point"],
                        "context": cf["context"],
                        "document_ids": cf.get("document_ids", [])
                    })
                yield {"status": f"Curation complete. Unified facts from {len(compiled_facts)} down to {len(final_facts)} premium entries."}
                await asyncio.sleep(0.05)
            except Exception as e:
                yield {"status": f"Warning: Curator error: {str(e)}. Using compiled facts as-is.", "warning": True}
                await asyncio.sleep(0.05)
                final_facts = compiled_facts
        else:
            final_facts = compiled_facts

        # 5. Save all finalized curated facts to the database
        yield {"status": f"Saving {len(final_facts)} curated facts to SQLite database..."}
        await asyncio.sleep(0.05)
        
        for fact_item in final_facts:
            # We map document_id to the first document in the references list
            doc_ids_list = fact_item.get("document_ids", [])
            primary_doc_id = doc_ids_list[0] if doc_ids_list else None
            # Fallback if primary_doc_id is not set
            if not primary_doc_id and docs:
                primary_doc_id = docs[0].id
                doc_ids_list = [primary_doc_id]
                
            serialized_doc_ids = ",".join(str(did) for did in doc_ids_list)
            
            db_fact = models.Fact(
                project_id=project_id,
                document_id=primary_doc_id,
                document_ids=serialized_doc_ids,
                point=fact_item["point"],
                context=fact_item["context"]
            )
            db.add(db_fact)
            
        await db.commit()
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
            session_id=session_id,
            state={"speaker_1": "{speaker_1}", "speaker_2": "{speaker_2}"}
        )
        
        runner = await self._get_runner(self.generation_workflow)
        
        # Combine facts and the user's guiding prompt
        full_prompt = f"""
        GUIDING PROMPT: {prompt}
        
        FACTS TO USE:
        {facts_str}
        
        Generate a highly conversational and engaging script based on these facts, following the guiding prompt.
        
        IMPORTANT STYLE REQUIREMENTS:
        1. SPEAKER NAMES: You must use the exact placeholders "{{speaker_1}}" and "{{speaker_2}}" (strictly lowercase with double curly braces in prompt, matching single curly braces in output text like {{speaker_1}}) for the speaker names. Do NOT use gendered or specific personal names.
        2. CHATTY & NATURAL TONE: Make the script highly conversational, informal, and dynamic:
           - The speakers MUST introduce themselves at the very beginning of the podcast (e.g. "Hi, I'm {{speaker_1}}!" and "And I'm {{speaker_2}}. Welcome back!").
           - The speakers MUST actively and frequently feed off what each other says. Use conversational transition hooks such as "yes exactly, {{speaker_1}}!", "that's fascinating... another thing I've found surprising about that is...", "oh absolutely", "I see what you mean", etc.
           - The dialogue should feel like a real, lively conversation, not two people alternately reading dry, isolated paragraphs. Use shorter sentences, rhetorical questions, light humor, and vocal agreement.
        3. SPOKEN DIALOGUE ONLY: Use ONLY spoken words. NO stage directions, NO music cues, NO sound effects.
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
            session_id=session_id,
            state={"speaker_1": "{speaker_1}", "speaker_2": "{speaker_2}"}
        )
        
        runner = await self._get_runner(self.generation_workflow)
        facts_str = json.dumps(facts, indent=2)
        
        full_prompt = f"""
        FACTS TO USE:
        {facts_str}
        
        Generate a highly conversational and engaging script based on these facts.
        
        IMPORTANT STYLE REQUIREMENTS:
        1. SPEAKER NAMES: You must use the exact placeholders "{{speaker_1}}" and "{{speaker_2}}" (strictly lowercase with double curly braces in prompt, matching single curly braces in output text like {{speaker_1}}) for the speaker names. Do NOT use gendered or specific personal names.
        2. CHATTY & NATURAL TONE: Make the script highly conversational, informal, and dynamic:
           - The speakers MUST introduce themselves at the very beginning of the podcast (e.g. "Hi, I'm {{speaker_1}}!" and "And I'm {{speaker_2}}. Welcome back!").
           - The speakers MUST actively and frequently feed off what each other says. Use conversational transition hooks such as "yes exactly, {{speaker_1}}!", "that's fascinating... another thing I've found surprising about that is...", "oh absolutely", "I see what you mean", etc.
           - The dialogue should feel like a real, lively conversation, not two people alternately reading dry, isolated paragraphs. Use shorter sentences, rhetorical questions, light humor, and vocal agreement.
        3. SPOKEN DIALOGUE ONLY: Use ONLY spoken words. NO stage directions, NO music cues, NO sound effects.
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

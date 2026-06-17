# %% [markdown]
# # AI辅助资治通鉴知识图谱挖掘&构建

# %%
import json

from IPython.display import Markdown

# %%
testing_mode = False  # Set to False to process all segments
book = json.load(open("adapted_book.json", "r"))
book[0]

# %%
from langchain_community.cache import SQLiteCache
from langchain_core.globals import set_llm_cache
from langchain_core.messages import HumanMessage, SystemMessage

set_llm_cache(SQLiteCache(database_path=".langchain.db"))

# %%
import os

from langchain_deepseek import ChatDeepSeek
from openai import OpenAI

# Create a ChatDeepSeek instance
chat_model = ChatDeepSeek(
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    temperature=0,
    # max_tokens=None,
    timeout=None,
    # max_retries=2,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    cache=True,
)

# Define a conversation
conversation = [
    SystemMessage("You are a helpful assistant."),
    HumanMessage("Hello!"),
]

# %%
# Remove environment variables if they exist
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("https_proxy", None)

# %%
sys_extraction_prompt = open("prompts/sys_entity_relation_extraction.md", "r").read()

chat_model = ChatDeepSeek(
    # Use deepseek-v4-pro for reasoning-heavy extraction passes.
    model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    temperature=0.1,
    max_tokens=None,
    timeout=None,
    max_retries=0,
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    cache=True,
    disable_streaming=True,
)

# %%
import os
import re
import json
import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from model.extraction import ExtractionResult, EntityRelationExtraction
from knowledge_store import KnowledgeStore, ChunkExtraction
from zztj_pipeline.llm_json import extract_json_from_response

# Initialize Knowledge Store
store = KnowledgeStore()
print(store.summary())



# Chunking configuration
CHUNK_SIZE = 1
CONTEXT_SIZE = 5

# Get unprocessed chunks
unprocessed_chunks = store.get_unprocessed_chunks(book, chunk_size=CHUNK_SIZE)
print(f"Found {len(unprocessed_chunks)} unprocessed chunks.")

# Filter to only handle 1 segment for testing
if unprocessed_chunks and False:
    first_juan = unprocessed_chunks[0][0]
    first_seg = unprocessed_chunks[0][1]
    unprocessed_chunks = [c for c in unprocessed_chunks if c[0] == first_juan and c[1] == first_seg]
    print(f"Testing mode: Processing only Juan {first_juan}, Seg {first_seg} ({len(unprocessed_chunks)} chunks).")

def process_chunk(chunk_info):
    juan_idx, seg_idx, chunk_start = chunk_info
    
    # Find the segment data
    juan_data = next(j for j in book if j["juan_index"] == juan_idx)
    segment_data = next(s for s in juan_data["segments"] if s["segment_index"] == seg_idx)
    sentences = segment_data['sentences']
    total_sentences = len(sentences)
    
    chunk_end = min(chunk_start + CHUNK_SIZE, total_sentences)
    chunk_sentences = sentences[chunk_start : chunk_end]
    
    # Context sentences
    context_start = max(0, chunk_start - CONTEXT_SIZE)
    context_sentences = sentences[context_start : chunk_start]

    # Format sentences with ORIGINAL indexes
    indexed_target_sentences = [f"[{chunk_start + j}]{sent}" for j, sent in enumerate(chunk_sentences)]
    indexed_context_sentences = [f"[{context_start + j}]{sent}" for j, sent in enumerate(context_sentences)]
    
    input_data = {
        "segment_index": seg_idx,
        "segment_start_time": segment_data['segment_start_time'],
        "context_sentences": indexed_context_sentences,
        "target_sentences": indexed_target_sentences,
        "note": f"Processing sentences {chunk_start} to {chunk_end - 1} of {total_sentences}."
    }
    
    # Define a conversation
    conversation = [
        SystemMessage(sys_extraction_prompt),
        HumanMessage(json.dumps(input_data, ensure_ascii=False, indent=2)),
    ]
    
    # Logging Request
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_prefix = f"debug_logs/req_{timestamp}_juan{juan_idx}_seg{seg_idx}_chunk{chunk_start}"
    
    with open(f"{log_prefix}_input.txt", "w") as f:
        f.write(sys_extraction_prompt + "\n\n" + json.dumps(input_data, ensure_ascii=False, indent=2))
        
    max_retries = 3
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            # Get a response from the model
            response = chat_model.invoke(conversation)
            
            # Logging Response
            suffix = f"_retry{attempt}" if attempt > 0 else ""
            with open(f"{log_prefix}_output{suffix}.txt", "w") as f:
                f.write(response.content)
                
            try:
                er_data = extract_json_from_response(response.content)
            except Exception as e:
                with open(f"{log_prefix}_error{suffix}.txt", "w") as f:
                    f.write(f"Error parsing JSON: {e}\n\nContent:\n{response.content}")
                raise e

            llm_extraction = EntityRelationExtraction(**er_data)
            
            # Post-process to add context info
            for entity in llm_extraction.entities:
                entity.juan_index = juan_idx
                entity.segment_index = seg_idx
                
            for location in llm_extraction.locations:
                location.juan_index = juan_idx
                location.segment_index = seg_idx
                
            for event in llm_extraction.events:
                event.juan_index = juan_idx
                event.segment_index = seg_idx
                
            for relation in llm_extraction.relations:
                relation.juan_index = juan_idx
                relation.segment_index = seg_idx
                
            # Extract token usage
            token_usage = response.response_metadata.get("token_usage", {})
            prompt_tokens = token_usage.get("prompt_tokens", 0)
            completion_tokens = token_usage.get("completion_tokens", 0)
            total_tokens = token_usage.get("total_tokens", 0)

            # Create ChunkExtraction object
            chunk_extraction = ChunkExtraction(
                juan_index=juan_idx,
                segment_index=seg_idx,
                chunk_start_index=chunk_start,
                chunk_end_index=chunk_end,
                segment_start_time=segment_data['segment_start_time'],
                source_sentences=chunk_sentences,
                entities=llm_extraction.entities,
                locations=llm_extraction.locations,
                events=llm_extraction.events,
                relations=llm_extraction.relations,
                model_name=chat_model.model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens
            )
            
            # Save to store
            store.save_chunk(chunk_extraction)
            return True, f"Saved chunk {chunk_start} for Juan {juan_idx}, Seg {seg_idx}."
            
        except Exception as e:
            last_exception = e
            print(f"Attempt {attempt + 1}/{max_retries} failed for chunk {chunk_start}: {e}")
            time.sleep(1) # Wait a bit before retrying
            
    return False, f"Error processing chunk {chunk_start} for Juan {juan_idx}, Seg {seg_idx} after {max_retries} attempts: {last_exception}"

# Process chunks with ThreadPoolExecutor
MAX_WORKERS = 16 # Adjust based on rate limits

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(process_chunk, chunk): chunk for chunk in unprocessed_chunks}
    
    for future in tqdm(as_completed(futures), total=len(unprocessed_chunks), desc="Processing Chunks"):
        success, message = future.result()
        if not success:
            print(message)

print("Processing complete.")
print(store.summary())

# %%
# Dump the Pydantic model to JSON (Example of exporting all data)
# json.dump(store._data, open('data/knowledge_store_dump.json', 'w'), ensure_ascii=False, indent=2)

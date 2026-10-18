"""
Knowledge Store: Progressive knowledge extraction storage management.

Manages persistent storage of extracted knowledge from historical texts,
supporting incremental updates and random access to any juan/segment/chunk.
"""

import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from pydantic import BaseModel, Field

from model.role import Role
from model.action import Action
from model.event import Event
from model.location import Location


class ChunkExtraction(BaseModel):
    """
    Extraction result for a single chunk of sentences.
    
    Key: (juan_index, segment_index, chunk_start_index)
    """
    juan_index: int
    segment_index: int
    chunk_start_index: int
    chunk_end_index: int
    segment_start_time: str
    source_sentences: List[str] = Field(default_factory=list)
    
    entities: List[Role] = Field(default_factory=list)
    locations: List[Location] = Field(default_factory=list)
    events: List[Event] = Field(default_factory=list)
    relations: List[Action] = Field(default_factory=list)
    
    extracted_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    model_name: str = ""
    
    # Token usage tracking
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    quality_notes: List[str] = Field(default_factory=list)
    

class KnowledgeStore:
    """
    Persistent storage for progressively extracted knowledge.
    
    Storage structure (Directory-based):
    data/store/
      metadata.json
      juan_1.json
      juan_2.json
      ...
    """
    
    def __init__(self, store_dir: str = "data/store"):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        # Migration check
        old_store_path = Path("data/knowledge_store.json")
        if old_store_path.exists():
            print("Migrating legacy knowledge_store.json to new structure...")
            self._migrate_legacy_store(old_store_path)
            
        self.metadata_path = self.store_dir / "metadata.json"
        self.metadata = self._load_metadata()
        
        # In-memory index of processed chunks: { "1-1-0", "1-1-1", ... }
        self._processed_keys = set()
        self._init_processed_keys()
        
        # Cache for the currently active juan data to reduce I/O
        self._current_juan_index = -1
        self._current_juan_data = {}

    def _load_metadata(self) -> Dict[str, Any]:
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "created_at": datetime.now().isoformat(),
            "version": "0.9",
            "progress": {
                "last_juan": 0,
                "last_segment": 0,
                "last_chunk": 0,
                "total_chunks_processed": 0
            }
        }

    def _save_metadata(self):
        self._atomic_save(self.metadata_path, self.metadata)

    @staticmethod
    def _atomic_save(path: Path, data):
        temp = path.with_suffix(path.suffix + '.tmp')
        with temp.open('w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)

    def _juan_file_path(self, juan_index: int) -> Path:
        return self.store_dir / f"juan_{juan_index}.json"

    def _load_juan_data(self, juan_index: int) -> Dict[str, Any]:
        path = self._juan_file_path(juan_index)
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_juan_data(self, juan_index: int, data: Dict[str, Any]):
        path = self._juan_file_path(juan_index)
        self._atomic_save(path, data)

    def _init_processed_keys(self):
        # Scan all juan files to populate the index
        for file_path in self.store_dir.glob("juan_*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._processed_keys.update(data.keys())
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

    def _migrate_legacy_store(self, old_path: Path):
        try:
            with open(old_path, 'r', encoding='utf-8') as f:
                old_data = json.load(f)
            
            # Migrate chunks
            chunks_by_juan = {}
            for key, chunk_data in old_data.get("chunks", {}).items():
                juan_idx = chunk_data["juan_index"]
                if juan_idx not in chunks_by_juan:
                    chunks_by_juan[juan_idx] = {}
                chunks_by_juan[juan_idx][key] = chunk_data
            
            for juan_idx, chunks in chunks_by_juan.items():
                self._save_juan_data(juan_idx, chunks)
            
            # Migrate metadata
            self.metadata_path = self.store_dir / "metadata.json"
            metadata = old_data.get("metadata", {})
            metadata["version"] = "2.0"
            metadata["progress"] = old_data.get("progress", {})
            with open(self.metadata_path, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
                
            print("Migration complete. Renaming old file to knowledge_store.json.bak")
            old_path.rename(old_path.with_suffix('.json.bak'))
            
        except Exception as e:
            print(f"Migration failed: {e}")

    @staticmethod
    def _make_key(juan_index: int, segment_index: int, chunk_start: int) -> str:
        """Create a unique key for a chunk."""
        return f"{juan_index}-{segment_index}-{chunk_start}"
    
    def save_chunk(self, extraction: ChunkExtraction):
        """
        Save or update a chunk extraction.
        Idempotent: calling with same key will overwrite.
        """
        # 1. Handle Juan Data
        if self._current_juan_index != extraction.juan_index:
            self._current_juan_index = extraction.juan_index
            self._current_juan_data = self._load_juan_data(extraction.juan_index)
        
        key = self._make_key(
            extraction.juan_index, 
            extraction.segment_index, 
            extraction.chunk_start_index
        )
        self._current_juan_data[key] = extraction.model_dump()
        self._save_juan_data(extraction.juan_index, self._current_juan_data)
        
        # 2. Update Index
        self._processed_keys.add(key)
        
        # 3. Update Metadata
        progress = self.metadata["progress"]
        if (extraction.juan_index > progress["last_juan"] or 
            (extraction.juan_index == progress["last_juan"] and 
             extraction.segment_index > progress["last_segment"]) or
            (extraction.juan_index == progress["last_juan"] and 
             extraction.segment_index == progress["last_segment"] and
             extraction.chunk_start_index > progress["last_chunk"])):
            progress["last_juan"] = extraction.juan_index
            progress["last_segment"] = extraction.segment_index
            progress["last_chunk"] = extraction.chunk_start_index
            
        progress["total_chunks_processed"] = len(self._processed_keys)
        self._save_metadata()
        
    def get_chunk(self, juan_index: int, segment_index: int, chunk_start: int) -> Optional[ChunkExtraction]:
        """Retrieve a specific chunk extraction."""
        if self._current_juan_index == juan_index:
            data = self._current_juan_data
        else:
            data = self._load_juan_data(juan_index)
            
        key = self._make_key(juan_index, segment_index, chunk_start)
        if key in data:
            return ChunkExtraction(**data[key])
        return None
    
    def has_chunk(self, juan_index: int, segment_index: int, chunk_start: int) -> bool:
        """Check if a chunk has been processed."""
        key = self._make_key(juan_index, segment_index, chunk_start)
        return key in self._processed_keys
    
    def delete_chunk(self, juan_index: int, segment_index: int, chunk_start: int) -> bool:
        """Delete a chunk extraction. Returns True if deleted."""
        # Load data if not current
        if self._current_juan_index == juan_index:
            data = self._current_juan_data
        else:
            data = self._load_juan_data(juan_index)
            
        key = self._make_key(juan_index, segment_index, chunk_start)
        if key in data:
            del data[key]
            self._save_juan_data(juan_index, data)
            
            if key in self._processed_keys:
                self._processed_keys.remove(key)
                
            self.metadata["progress"]["total_chunks_processed"] = len(self._processed_keys)
            self._save_metadata()
            
            # Update current cache if needed
            if self._current_juan_index == juan_index:
                self._current_juan_data = data
            return True
        return False
    
    def get_segment_chunks(self, juan_index: int, segment_index: int) -> List[ChunkExtraction]:
        """Get all chunks for a specific segment."""
        data = self._load_juan_data(juan_index)
        prefix = f"{juan_index}-{segment_index}-"
        chunks = []
        for key, chunk_data in data.items():
            if key.startswith(prefix):
                chunks.append(ChunkExtraction(**chunk_data))
        return sorted(chunks, key=lambda x: x.chunk_start_index)
    
    def get_juan_chunks(self, juan_index: int) -> List[ChunkExtraction]:
        """Get all chunks for a specific juan."""
        data = self._load_juan_data(juan_index)
        chunks = []
        for chunk_data in data.values():
            chunks.append(ChunkExtraction(**chunk_data))
        return sorted(chunks, key=lambda x: (x.segment_index, x.chunk_start_index))
    
    def get_all_entities(self) -> List[Role]:
        """Aggregate all entities from all chunks."""
        entities = []
        for file_path in self.store_dir.glob("juan_*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for chunk_data in data.values():
                    for e in chunk_data.get("entities", []):
                        entities.append(Role(**e))
        return entities
    
    def get_all_locations(self) -> List[Location]:
        """Aggregate all locations from all chunks."""
        locations = []
        for file_path in self.store_dir.glob("juan_*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for chunk_data in data.values():
                    for loc in chunk_data.get("locations", []):
                        locations.append(Location(**loc))
        return locations
    
    def get_all_events(self) -> List[Event]:
        """Aggregate all events from all chunks."""
        events = []
        for file_path in self.store_dir.glob("juan_*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for chunk_data in data.values():
                    for e in chunk_data.get("events", []):
                        events.append(Event(**e))
        return events
    
    def get_all_relations(self) -> List[Action]:
        """Aggregate all relations from all chunks."""
        relations = []
        for file_path in self.store_dir.glob("juan_*.json"):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for chunk_data in data.values():
                    for r in chunk_data.get("relations", []):
                        relations.append(Action(**r))
        return relations
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress info."""
        return self.metadata["progress"].copy()
    
    def get_unprocessed_chunks(self, book: List[Dict], chunk_size: int = 10) -> List[tuple]:
        """
        Given a book structure, return list of (juan_idx, seg_idx, chunk_start) 
        that have not been processed yet.
        """
        unprocessed = []
        for juan in book:
            juan_idx = juan["juan_index"]
            for segment in juan["segments"]:
                seg_idx = segment["segment_index"]
                sentences = segment["sentences"]
                for chunk_start in range(0, len(sentences), chunk_size):
                    if not self.has_chunk(juan_idx, seg_idx, chunk_start):
                        unprocessed.append((juan_idx, seg_idx, chunk_start))
        return unprocessed
    
    def summary(self) -> str:
        """Get a summary of the store."""
        progress = self.metadata["progress"]
        
        total_entities = 0
        total_locations = 0
        total_events = 0
        total_relations = 0
        
        for file_path in self.store_dir.glob("juan_*.json"):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for chunk_data in data.values():
                        total_entities += len(chunk_data.get("entities", []))
                        total_locations += len(chunk_data.get("locations", []))
                        total_events += len(chunk_data.get("events", []))
                        total_relations += len(chunk_data.get("relations", []))
            except Exception:
                pass
        
        return f"""Knowledge Store Summary:
- Total chunks processed: {progress['total_chunks_processed']}
- Last processed: Juan {progress['last_juan']}, Segment {progress['last_segment']}, Chunk {progress['last_chunk']}
- Total entities: {total_entities}
- Total locations: {total_locations}
- Total events: {total_events}
- Total relations: {total_relations}
"""


if __name__ == "__main__":
    # Demo usage
    store = KnowledgeStore()
    print(store.summary())

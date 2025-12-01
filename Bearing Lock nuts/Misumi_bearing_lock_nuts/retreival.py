import time
from fastembed import TextEmbedding,SparseTextEmbedding,LateInteractionTextEmbedding
from qdrant_client import QdrantClient,models
client=QdrantClient(url="http://localhost:6333")
collection_name="Misumi Bearing Lock Nuts"
dense_encoder=TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
sparse_encoder=SparseTextEmbedding("Qdrant/bm25")
lateInteraction=LateInteractionTextEmbedding("colbert-ir/colbertv2.0")

def embed_query(query):
    start_time=time.perf_counter()
    dense_embed=next(dense_encoder.query_embed(query))
    sparse_embed=next(sparse_encoder.query_embed(query))
    late_embed=next(lateInteraction.query_embed(query))
    end_time=time.perf_counter()
    print(f"Time required for embedding generation:{end_time-start_time:.4f} seconds")
    return dense_embed,sparse_embed,late_embed

def chunk_retrieval(query):
    dense_vectors,sparse_vectors,late_vectors=embed_query(query)
    prefetch=[
        models.Prefetch(query=dense_vectors,using="dense",limit=20,),
        models.Prefetch(query=models.SparseVector(**sparse_vectors.as_object()),using="sparse",limit=20),
    ]
    start_qdrant=time.perf_counter()
    query_results=client.query_points(
        collection_name=collection_name,
        prefetch=prefetch,
        query=late_vectors,
        using="lateInteraction",
        limit=10,
        with_payload=True,
        with_vectors=False
    ).points
    end_qdrant=time.perf_counter()
    print(f"Timing required for Qdrant search and retreival:{end_qdrant-start_qdrant:.4f} seconds")

    return query_results
    
def retrieval_misumi(query):
    retrieved_docs=chunk_retrieval(query)    
    all_chunks=[]
    for point in retrieved_docs:
            chunk_desc=point.payload.get("chunk")
            all_chunks.append(chunk_desc)
        
    return all_chunks

if __name__=="__main__":
     print("The retrived part numbers are:")
     points =retrieval_misumi(query = "bearing lock nut hexagon")
     for point in points:
        print(f"{point}\n\n")
    




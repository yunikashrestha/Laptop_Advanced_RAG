import os
import pandas as pd
import uuid
from fastembed import TextEmbedding, SparseTextEmbedding, LateInteractionTextEmbedding
from qdrant_client import QdrantClient, models
import time

file_name = "nsk_bulk_data.xlsx"
collection_name = "NSK Bearing Lock Nuts"
dense_encoder = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
sparse_encoder = SparseTextEmbedding("Qdrant/bm25")
late_encoder = LateInteractionTextEmbedding("colbert-ir/colbertv2.0")

df=pd.read_excel(file_name)
category_name="Bearing Lock nuts"
client=QdrantClient(url="http://localhost:6333")
   

def combine_row_parts(row):
    parts = []
    sub_category_name=row.get("Product Name","N/A")
   
    for col_name, value in row.items():
        
        if pd.notna(value):
            parts.append(f"{col_name}: {value}")
    parts.append(f"Category: {category_name}")
    parts.append(f"Sub Category: {sub_category_name}")
    parts.append("Website: NSK")
    return " | ".join(parts)
df["combined_text"] = df.apply(combine_row_parts, axis=1)


def create_collection_payload():
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(
                    size=dense_encoder.embedding_size,
                    distance=models.Distance.COSINE
                ),
                "lateInteraction":models.VectorParams(
                    size=late_encoder.embedding_size,
                    distance=models.Distance.COSINE,
                    multivector_config=models.MultiVectorConfig(
                        comparator=models.MultiVectorComparator.MAX_SIM
                    ),
                ),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(modifier=models.Modifier.IDF)
            },
        )
        client.create_payload_index(collection_name=collection_name,field_name="product_id",field_schema="integer")
        client.create_payload_index(collection_name=collection_name,field_name="chunk_id",field_schema="integer")
        client.create_payload_index(collection_name=collection_name,field_name="part_number",field_schema="keyword")
        client.create_payload_index(collection_name=collection_name,field_name="category_name",field_schema="keyword")
        client.create_payload_index(collection_name=collection_name,field_name="subcategory_name",field_schema="keyword")
        client.create_payload_index(collection_name=collection_name,field_name="website",field_schema="keyword")
        client.create_payload_index(collection_name=collection_name,field_name="chunk",field_schema="keyword")
        client.create_payload_index(collection_name=collection_name,field_name="URL",field_schema="keyword")
        

def to_vectordb():
     

    create_collection_payload()
    texts=df["combined_text"].tolist()

    offset = 0
    subcategory_offset = 0
    info = client.get_collection(collection_name=collection_name)
    count = info.points_count
    if(count != 0):
        res,_ = client.scroll(
            collection_name = collection_name,
            limit = 1,
            with_payload = True,
            with_vectors = False,
            order_by={
                "key" : "chunk_id",
                "direction" : "desc"
            }
        )
        if(res):
            chunk_id_num= res[0].payload.get("chunk_id")
            subcategory_id_num=res[0].payload.get("product_id")
            offset = chunk_id_num + 1
            subcategory_offset=subcategory_id_num+1
            

        else:
            offset = 0
            subcategory_offset = 0
    else:
        offset = 0
        subcategory_offset = 0

    num_points=len(df)
    total_start_time=time.perf_counter()
    row_timings=[]

    for i,row in df.iterrows():
        row_start_time = time.perf_counter()
        client.upsert(
            collection_name = collection_name,
            points = [
                models.PointStruct(
                    id = offset,
                    payload = {
                            "product_id" :subcategory_offset,
                            "chunk_id" : offset,
                            "part_number":row["Product Name"],
                            "category_name" : category_name,
                            "sub_category_name":row["Product Name"],
                            "website" :"NSK",
                            "chunk" : row["combined_text"],
                            "URL" :row["URL"]
                        },
                    vector = {
                            "dense" : list(dense_encoder.embed(row["combined_text"]))[0],
                            "sparse" : list(sparse_encoder.embed(row["combined_text"]))[0].as_object(),
                            "lateInteraction" : list(late_encoder.embed(row["combined_text"]))[0]
                        }
                    )
                ]
            )
        row_end_time = time.perf_counter() # End timer for the current row
        row_duration = row_end_time - row_start_time
        row_timings.append({
            "chunk_id": offset,
            "part_number": row["Product Name"],
            "time_seconds": f"{row_duration:.6f}"
        })
        offset=offset+1
        subcategory_offset=subcategory_offset+1
    total_end_time=time.perf_counter()
    total_elapsed_time=total_end_time-total_start_time
    average_time=total_elapsed_time/num_points if num_points>0 else 0
          

    output_message=(
    f"File Inserted :{file_name} \n"
    f"Total Points Inserted: {num_points}\n"
    f"Total time required:{total_elapsed_time:.4f} seconds \n"
    f"Average Time Required: {average_time} \n\n "
    )
    print(output_message)
    report_filename="insertion_time.txt"
    with open(report_filename,"a") as f:
        f.write(output_message + "\n")



if __name__=="__main__":
    to_vectordb()
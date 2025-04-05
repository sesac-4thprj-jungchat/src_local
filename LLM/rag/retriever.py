"""
검색 관련 기능을 제공하는 모듈
"""
import os
import time
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from langchain.retrievers.contextual_compression import ContextualCompressionRetriever
from langchain_cohere import CohereRerank
from langchain.retrievers import BM25Retriever, EnsembleRetriever

from config import TOP_K_RERANK, VECTORSTORE_A_PATH, JSON_FILE_PATH
from embedding import get_embedding_model
from step_back_rerank import StepBackRAG

# StepBackRAG 인스턴스 생성
RAG = StepBackRAG(vectorstore_path=VECTORSTORE_A_PATH, json_data_path=JSON_FILE_PATH)

def rerank_documents_and_extract_service_ids(documents: List[Document], question: str, top_k: int = 15) -> List[str]:
    """Re-ranking을 통해 문서 목록을 정렬한 후, 각 문서의 서비스ID 리스트를 반환"""
    load_dotenv()
    COHERE_API_KEY = os.getenv("COHERE_API_KEY")
    
    if not COHERE_API_KEY:
        print("COHERE_API_KEY가 설정되지 않았습니다.")
        return [doc.metadata.get("서비스ID", "미확인") for doc in documents[:top_k]]
    
    try:
        compressor = CohereRerank(model="rerank-multilingual-v3.0", top_n=top_k, cohere_api_key=COHERE_API_KEY)

        # 타이밍 측정: FAISS 벡터스토어 생성
        t0 = time.time()
        embedding_model = get_embedding_model()
        vectorstore = FAISS.from_documents(documents, embedding_model)
        t1 = time.time()
        print(f"[타이밍] FAISS 벡터스토어 생성: {t1 - t0:.2f} 초")

        # retriever 객체 생성
        base_retriever = vectorstore.as_retriever()

        t2 = time.time()
        compression_retriever = ContextualCompressionRetriever(
            base_compressor=compressor, base_retriever=base_retriever
        )
        t3 = time.time()
        print(f"[타이밍] CompressionRetriever 생성: {t3 - t2:.2f} 초")
        
        # 질문에 따른 압축 및 점수 계산 결과를 얻음
        t4 = time.time()
        compressed_docs = compression_retriever.invoke(question)
        t5 = time.time()
        print(f"[타이밍] Re-ranking (문서 압축 및 점수 계산): {t5 - t4:.2f} 초")

        print(f"compressed_docs 길이: {len(compressed_docs)}")  # 디버깅용 출력
        
        # 압축된 문서에서 서비스ID 추출
        service_ids = [doc.metadata.get("서비스ID", "미확인") for doc in compressed_docs[:top_k]]
        print(f"service_ids 길이: {len(service_ids)}")  # 디버깅용 출력

        if not service_ids:
            return []  # 빈 리스트 반환
            
        return service_ids
    except Exception as e:
        print(f"rerank_documents_and_extract_service_ids 에러 발생: {e}")
        # 에러 발생 시 원본 문서에서 서비스ID 추출
        return [doc.metadata.get("서비스ID", "미확인") for doc in documents[:top_k]]

async def get_similarity_results(question: str, stepback_question: str) -> List[str]:
    """정보1 수집: A 벡터스토어에서 문서 검색 및 Re-ranking"""
    print("정보1 수집 시작...")
    try:
        docs = RAG.retrieve_with_step_back(question, stepback_question)
        doc_ids = []
        for doc in docs:
            doc_id = doc.metadata.get("서비스ID")
            if doc_id:
                doc_ids.append(doc_id)
                
        print(f"정보1 수집 완료: {len(doc_ids)}개 문서 ID 수집")
        return doc_ids
    except Exception as e:
        print(f"get_similarity_results 에러 발생: {e}")
        return []

def ensemble_document_BM25_FAISS(documents: List[Document], question: str, top_k: int = 15) -> List[str]:
    # 타이밍 시작
    t0 = time.time()
    
    # BM25 리트리버 초기화 (후보 문서 개수를 top_k의 2배로 설정)
    bm25_retriever = BM25Retriever.from_documents(documents)
    bm25_retriever.k = 2 * top_k
    
    # 임베딩 모델 로드
    embedding_model = get_embedding_model()
    
    # FAISS 벡터 스토어 로드 (VECTORSTORE_A_PATH를 FAISS 객체로 불러옴)
    faiss_vectorstore = FAISS.load_local(VECTORSTORE_A_PATH, embedding_model=embedding_model)
    faiss_retriever = faiss_vectorstore.as_retriever(search_kwargs={"k": top_k})
    
    # 앙상블 리트리버 초기화 (BM25와 FAISS의 결과를 동일한 가중치로 합침)
    ensemble_retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, faiss_retriever],
        weights=[0.5, 0.5]
    )
    
    t1 = time.time()
    print(f"[타이밍] 앙상블 리트리버 생성: {t1 - t0:.2f} 초")
    
    # 앙상블 리트리버를 통해 재랭킹된 문서들을 가져옴
    reranked_documents = ensemble_retriever.invoke(question)
    
    # 문서의 메타데이터에서 "서비스ID"를 추출 (없으면 "미확인")
    service_ids = [doc.metadata.get("서비스ID", "미확인") for doc in reranked_documents]
    print(f"service_ids 길이: {len(service_ids)}")
    
    t2 = time.time()
    print(f"[타이밍] 앙상블 리랭킹 끝: {t2 - t1:.2f} 초")
    
    return service_ids if service_ids else []


def convert_dicts_to_documents(docs_dict: List[Dict[str, Any]]) -> List[Document]:
    """딕셔너리 리스트에서 Document 객체 리스트로 변환"""
    documents = []
    for doc in docs_dict:
        support_detail = doc.get('지원내용', '') or ''
        service_summary = doc.get('서비스목적요약', '') or ''
        service_category = doc.get("서비스분야") or ''
        required_summary = doc.get("선정기준") or ''
        if not (support_detail.strip() or service_summary.strip() or service_category.strip() or required_summary.strip()):
            continue
        
        page_content = f"{support_detail}\n{service_summary}\n{service_category}\n{required_summary}".strip()
        
        document = Document(
            page_content=page_content,
            metadata={
                '서비스ID': doc.get('서비스ID', ''),
                '서비스명': doc.get('서비스명', ''),
            }
        )
        documents.append(document)
    return documents
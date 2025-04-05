from langchain_huggingface import HuggingFaceEmbeddings
import pandas as pd
from langchain.schema import Document
from langchain_community.vectorstores import FAISS
from config import EMBEDDING_MODEL, QUERY_VECTOR_STORE_PATH, QUERY_DATA_PATH
# 전역 변수로 임베딩 모델 캐싱
_embedding_model = None
QUERY_VECTOR_STORE = None


def get_embedding_model():
    """임베딩 모델을 싱글톤 패턴으로 로드"""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return _embedding_model


def get_question_vectorstore():
    """질문 벡터스토어를 싱글톤 패턴으로 로드

    우선 지정된 로컬 경로에서 벡터스토어를 로드하고,
    실패할 경우 CSV 파일을 읽어 벡터스토어를 생성하는 대체 로직을 수행합니다.
    """
    global QUERY_VECTOR_STORE 

    if QUERY_VECTOR_STORE is None:
        embedding_model = get_embedding_model()
        try:
            # QUESTION_VECTORSTORE_PATH 대신 QUERY_VECTOR_STORE_PATH 사용
            QUERY_VECTOR_STORE = FAISS.load_local(
                QUERY_VECTOR_STORE_PATH, 
                embedding_model,
                allow_dangerous_deserialization=True  # 신뢰할 수 있는 소스에서만 사용
            )
            print(f"질문 벡터스토어 로드 완료: {QUERY_VECTOR_STORE_PATH}")
        except Exception as e:
            print(f"질문 벡터스토어 로드 실패: {e}")
            print("대체 로직 사용 중 (CSV 파일 기반 벡터스토어 생성)...")
            try:
                # CSV 파일 읽기 및 Document 객체 생성
                df = pd.read_csv(QUERY_DATA_PATH)
                documents = []
                for _, row in df.iterrows():
                    # 'query' 컬럼은 임베딩할 텍스트, 'generated_sql' 컬럼은 metadata에 저장
                    page_content = row.get('query', '')
                    metadata = {
                        'generated_sql': row.get('generated_sql', '')
                    }
                    documents.append(Document(page_content=page_content, metadata=metadata))
                
                # allow_dangerous_deserialization 매개변수 제거
                QUERY_VECTOR_STORE = FAISS.from_documents(
                    documents, 
                    embedding_model
                )
                
                # 벡터스토어 생성 후 저장 추가
                QUERY_VECTOR_STORE.save_local(QUERY_VECTOR_STORE_PATH)
                print("CSV 기반 질문 벡터스토어 생성 및 저장 완료")
            except Exception as e2:
                print(f"대체 로직 실패: {e2}")
                QUERY_VECTOR_STORE = None
    return QUERY_VECTOR_STORE
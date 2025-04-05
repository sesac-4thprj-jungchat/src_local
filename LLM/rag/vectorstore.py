"""
벡터스토어 관리를 위한 모듈
"""
from langchain_community.vectorstores import FAISS
from config import VECTORSTORE_A_PATH
from embedding import get_embedding_model
import pandas as pd 
from langchain.schema import Document
from langchain_huggingface import HuggingFaceEmbeddings
import torch

# 전역 변수로 벡터스토어 캐싱
_vectorstore_a = None

# CUDA 및 MPS 가용성 확인을 위한 함수 추가
def get_device():
    """CUDA 또는 MPS 가용성을 확인하고 적절한 디바이스를 반환합니다."""
    try:
        if torch.cuda.is_available():
            print("CUDA 사용 가능 - NVIDIA GPU를 사용합니다.")
            return 'cuda'
        elif hasattr(torch, 'backends') and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            print("MPS 사용 가능 - Apple Silicon(M1/M2) GPU를 사용합니다.")
            return 'mps'
        else:
            print("GPU 가속 사용 불가능 - CPU를 사용합니다.")
            return 'cpu'
    except ImportError:
        print("PyTorch를 찾을 수 없습니다 - CPU를 사용합니다.")
        return 'cpu'
    except Exception as e:
        print(f"디바이스 확인 중 오류 발생: {e} - CPU를 사용합니다.")
        return 'cpu'

def load_vectorstore_a():
    """벡터스토어 A를 로드하는 함수"""
    try:
        # 적절한 디바이스 선택
        device = get_device()
        
        # 임베딩 모델 생성 필요
        embedding_model = HuggingFaceEmbeddings(
            model_name="dragonkue/snowflake-arctic-embed-l-v2.0-ko",
            model_kwargs={'device': device},
            encode_kwargs={'normalize_embeddings': True}
        )
        
        # 임베딩 모델을 인자로 전달
        return FAISS.load_local(
            VECTORSTORE_A_PATH, 
            embedding_model,
            allow_dangerous_deserialization=True
        )
    except Exception as e:
        print(f"벡터스토어 A 로드 실패: {e}")
        return None


import os
from dotenv import load_dotenv
from openai import OpenAI
import httpx
import json

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

async def request_gpt(message: str, conversation_history: str = "", rag_context: str = "", user_info: str = "", is_policy_question: bool = False):
    try:
        # 시스템 프롬프트 설정
        system_prompt = """당신은 친절하고 전문적인 AI 어시스턴트입니다. """

        system_prompt_rag = f"""당신은 사용자 맞춤형 정부 정책 추천 시스템입니다.

사용자 정보:
- 성별: {user_info.get("gender", "미지정")}
- 지역: {user_info.get("area", "미지정")}
- 특성: {user_info.get("personalCharacteristics", "미지정")}

아래는 이 사용자에게 적합한 보조금/지원 정책 요약 리스트입니다:

{rag_context}

이 정책들을 기반으로, 아래와 같은 형식으로 **전체 사용자 맞춤 요약**을 작성하세요:

1. 이 사용자가 어떤 생활환경 또는 상황에 처해있다고 판단되는지 (ex: 저소득 맞벌이 가구, 어린 자녀가 있는 가정 등)
2. 이러한 상황에 왜 위 정책들이 도움이 될 수 있는지 설명
3. 이 중 몇몇 정책은 **최대 얼마까지** 지원이 가능한지 언급
4. 마지막 "자세한 내용은 각 정책의 링크를 참고해 주세요." 이 내용 추가

모든 내용은 총 5~8문장으로 구성하고, 정책 하나만 말하지 말고 **전체를 종합적으로 설명**하세요."""

        # 메시지 배열 준비
        messages = []
        valid_roles = {"system", "assistant222", "user111", "function", "tool", "developer"}

        # RAG 컨텍스트가 있으면 프롬프트에 포함
        if is_policy_question:
            # 정책 전문가 프롬프트로 변경
 
            messages.append({"role": "system", "content": system_prompt_rag})
            messages.append({"role": "system", "content": rag_context})
        else:
            # 일반 대화인 경우 기본 시스템 프롬프트 사용
            messages.append({"role": "system", "content": system_prompt})

        # 대화 기록 처리
        if conversation_history:
            lines = conversation_history.strip().split('\n')
            for line in lines:
                if line.startswith("사용자 정보:"):
                    messages.append({"role": "system", "content": line})
                else:
                    try:
                        role, content = line.split("::: ", 1)
                        if role not in valid_roles:
                            messages.append({"role": "user", "content": line})
                        else:
                            if role == "user111":
                                role = "user"
                            elif role == "assistant222":
                                role = "assistant"
                            messages.append({"role": role, "content": content})
                    except ValueError:
                        messages.append({"role": "user", "content": line})

        # 사용자 메시지 추가
        messages.append({"role": "user", "content": message})

        # GPT 호출
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )
        gpt_response = completion.choices[0].message.content
    except Exception as e:
        gpt_response = f"죄송합니다. 서비스 연결에 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
        print(f"GPT API 호출 중 에러 발생: {str(e)}")

    return gpt_response
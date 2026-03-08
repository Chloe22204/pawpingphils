import dashscope
from dashscope import Generation

response = Generation.call(
    model="qwen-turbo",
    prompt="Say hello"
)

print(response)


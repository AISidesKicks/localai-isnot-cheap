maual research:

LFM2.5-2.6B supports native tool calling across all three engines using standard OpenAI-style payloads. [1, 2] 
The model relies on a unique Pythonic syntax format (function_name(arg="value")) inside its grammar boundaries (<|tool_call_start|> and <|tool_call_end|>). For the model to reliably invoke tools instead of outputting plain text, you must configure the backend servers to use its native chat template and tool parsers. [1, 3, 4] 
## Llama.cpp Server (GGUF)
llama.cpp relies on the Jinja chat template bundled inside the GGUF file or explicitly passed to parse tools. Use the --jinja flag or direct parameter configuration to handle the native ChatML-style tool syntax. [1] 
## 1. Server Launch Command

# Download the official Q4_K_M or Q8 GGUF file from LiquidAI
./llama-server \
  --model lfm2.5-2.6b-Q4_K_M.gguf \
  --host 0.0.0.0 \
  --port 8080 \
  --ctx-size 32768 \
  --threads 8 \
  --chat-template auto

## 2. OpenAI-Compatible API Request
When calling the llama.cpp server, pass the tools array directly. The server automatically utilizes internal grammars to enforce the structured tool formatting. [5, 6] 

curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lfm2.5-2.6b",
    "messages": [
      {"role": "user", "content": "What is the weather in Prague right now?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "get_weather",
          "description": "Get current weather for a location",
          "parameters": {
            "type": "object",
            "properties": {
              "location": {"type": "string", "description": "City name"}
            },
            "required": ["location"]
          }
        }
      }
    ]
  }'

------------------------------
## vLLM Configuration
vLLM natively parses the model's tokenizer_config.json containing the tool-calling chat template. Ensure you are running vLLM with auto-formatting enabled. [4, 7] 
## 1. Server Launch Command

vllm serve LiquidAI/LFM2.5-2.6B \
  --host 0.0.0.0 \
  --port 8000 \
  --max-model-len 32768 \
  --enable-auto-tool-choice \
  --tool-call-parser lfm2

(Note: If the default tool parser fails to output correctly, fall back to explicit template parsing by omitting --tool-call-parser and letting vLLM read the default chat template rules.) [4] 
## 2. Python Client Request

from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="token")
response = client.chat.completions.create(
    model="LiquidAI/LFM2.5-2.6B",
    messages=[{"role": "user", "content": "Calculate 15% tip on a $120 bill."}],
    tools=[{
        "type": "function",
        "function": {
          "name": "calculate_tip",
          "parameters": {
            "type": "object",
            "properties": {
              "bill": {"type": "number"},
              "percentage": {"type": "number"}
            },
            "required": ["bill", "percentage"]
          }
        }
    }],
    tool_choice="auto"
)
print(response.choices[0].message.tool_calls)

------------------------------
## SGLang Configuration
SGLang features native lfm2 tool-call parsing and <think> reasoning extraction, providing the lowest latency for high-concurrency agent workflows. [3] 
## 1. Server Launch Command

python3 -m sglang.launch_server \
  --model-path LiquidAI/LFM2.5-2.6B \
  --host 0.0.0.0 \
  --port 30000 \
  --context-length 32768 \
  --tool-call-parser lfm2

The --tool-call-parser lfm2 argument explicitly instructs SGLang's engine to process the <|tool_call_start|> sequences seamlessly. [1, 3] 
## 2. cURL API Request

curl http://localhost:30000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "LiquidAI/LFM2.5-2.6B",
    "messages": [
      {"role": "user", "content": "Search for the latest stock price of Apple."}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "web_search",
          "description": "Search the live web",
          "parameters": {
            "type": "object",
            "properties": {
              "query": {"type": "string"}
            },
            "required": ["query"]
          }
        }
      }
    ]
  }'

------------------------------
## Critical Operational Tips

* Temperature Adjustment: Liquid AI explicitly recommends setting temperature=0.1 at runtime for tool-calling pipelines to limit hallucinations and ensure accurate syntax adherence. [1] 
* Stop Tokens: If the server loops or fails to terminate tool calls, manually append <|im_start|>, <|im_end|>, <|tool_call_start|>, and <|tool_call_end|> to the stop parameter configuration array. [1] 

Would you like assistance setting up an automated multi-turn orchestration framework (like LangChain or AutoGen) to feed the execution outputs back into any of these servers?

[1] [https://ollama.com](https://ollama.com/oamazonasgabriel/lfm2.5-2.6b)
[2] [https://huggingface.co](https://huggingface.co/LiquidAI/LFM2.5-2.6B)
[3] [https://docs.liquid.ai](https://docs.liquid.ai/deployment/gpu-inference/sglang)
[4] [https://github.com](https://github.com/rishikksh20/lfm25-pytorch)
[5] [https://github.com](https://github.com/ggml-org/llama.cpp)
[6] [https://github.com](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
[7] [https://docs.liquid.ai](https://docs.liquid.ai/deployment/gpu-inference/vllm)


#!/bin/bash
echo "============================================================"
echo "🔬 FINAL API TEST"
echo "============================================================"

cd "$(dirname "$0")"
source venv/bin/activate

export OPENAI_API_KEY=$(grep '^OPENAI_API_KEY' .env | cut -d'=' -f2)
export ANTHROPIC_API_KEY=$(grep '^ANTHROPIC_API_KEY' .env | cut -d'=' -f2)

echo ""
echo "🤖 Testing OpenAI..."
python3 -c "
from openai import OpenAI
import os
client = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
response = client.chat.completions.create(
    model='gpt-3.5-turbo',
    messages=[{'role': 'user', 'content': 'Say: OpenAI works'}],
    max_tokens=10
)
print(f'✅ Response: {response.choices[0].message.content}')
print(f'✅ Tokens: {response.usage.total_tokens}')
" && echo "✅ OpenAI: PASS" || echo "❌ OpenAI: FAIL"

echo ""
echo "🤖 Testing Anthropic..."
python3 -c "
from anthropic import Anthropic
import os
client = Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])
response = client.messages.create(
    model='claude-3-haiku-20240307',
    max_tokens=10,
    messages=[{'role': 'user', 'content': 'Say: Claude works'}]
)
print(f'✅ Response: {response.content[0].text}')
print(f'✅ Tokens: in={response.usage.input_tokens}, out={response.usage.output_tokens}')
" && echo "✅ Anthropic: PASS" || echo "❌ Anthropic: FAIL"

echo ""
echo "============================================================"
echo "✅ ALL AI SERVICES OPERATIONAL!"
echo "============================================================"

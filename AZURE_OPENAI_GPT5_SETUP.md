# Azure OpenAI và GPT-5-Mini Setup Guide

Tài liệu này ghi lại các thay đổi cần thiết để cấu hình Azure OpenAI và thêm hỗ trợ cho model GPT-5-mini trong dự án Screenshot-to-Code.

## 🔧 Cấu hình Azure OpenAI

### 1. File `.env` Configuration

Tạo file `backend/.env` với nội dung sau:

```env
# Azure OpenAI Configuration - Using dedicated Azure OpenAI resource
# Resource: sc-to-code-azure-openai.openai.azure.com

# Your Azure OpenAI API Key (from sc-to-code-azure-openai resource)
AZURE_OPENAI_API_KEY=your-azure-openai-api-key-here

# Azure OpenAI Resource Name
AZURE_OPENAI_RESOURCE_NAME=SC-TO-CODE-Azure-OpenAI

# Your GPT-5-mini deployment name (check Model deployments in Azure Portal)
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-5-mini

# API version
AZURE_OPENAI_API_VERSION=2024-12-01-preview

# Your DALL-E 3 deployment name (if you have one)
AZURE_OPENAI_DALLE3_DEPLOYMENT_NAME=SC-TO-CODE-Azure-OpenAI-dall-e-3

# API version for DALL-E 3
AZURE_OPENAI_DALLE3_API_VERSION=3.0

# Optional: If you want to use Anthropic Claude
# ANTHROPIC_API_KEY=your-anthropic-key-here
```

### 2. Fix API Key Validation Logic

**File**: `backend/routes/generate_code.py`

**Vấn đề**: Code chỉ kiểm tra `OPENAI_API_KEY` hoặc `ANTHROPIC_API_KEY`, không nhận diện Azure OpenAI configuration.

**Giải pháp**: Thêm logic kiểm tra Azure OpenAI configuration vào validation.

```python
# Thêm vào khoảng dòng 261-267
# Check if Azure OpenAI configuration is available
azure_openai_available = (
    os.environ.get("AZURE_OPENAI_API_KEY") and
    os.environ.get("AZURE_OPENAI_RESOURCE_NAME") and
    os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME") and
    os.environ.get("AZURE_OPENAI_API_VERSION")
)

# Sửa điều kiện validation
if openai_api_key and anthropic_api_key:
    variant_models = [claude_model, Llm.GPT_5_MINI]
elif openai_api_key or azure_openai_available:  # ← Thêm azure_openai_available
    variant_models = [Llm.GPT_5_MINI, Llm.GPT_5_MINI]
elif anthropic_api_key:
    variant_models = [claude_model, Llm.CLAUDE_3_5_SONNET_2024_06_20]
else:
    await throw_error(
        "No OpenAI, Azure OpenAI, or Anthropic API key found. Please add the appropriate API key in the settings dialog or backend/.env."
    )
    raise Exception("No OpenAI, Azure OpenAI, or Anthropic key")
```

## 🤖 Thêm Support cho GPT-5-Mini

### 1. Thêm Model Definition

**File**: `backend/llm.py`

```python
# Thêm vào enum Llm (khoảng dòng 25)
class Llm(Enum):
    GPT_4_VISION = "gpt-4-vision-preview"
    GPT_4_TURBO_2024_04_09 = "gpt-4-turbo-2024-04-09"
    GPT_4O_2024_05_13 = "gpt-4o-2024-05-13"
    GPT_4O_2024_08_06 = "gpt-4o-2024-08-06"
    GPT_4O_2024_11_20 = "gpt-4o-2024-11-20"
    GPT_5_MINI = "gpt-5-mini"  # ← Thêm dòng này
    CLAUDE_3_SONNET = "claude-3-sonnet-20240229"
    # ... rest of models
```

### 2. Cấu hình Model Parameters

**File**: `backend/llm.py`

GPT-5-mini có đặc điểm riêng:
- Không hỗ trợ `max_tokens`, phải dùng `max_completion_tokens`
- Không hỗ trợ streaming
- Không hỗ trợ temperature

```python
# Sửa stream configuration (khoảng dòng 84)
if model not in (Llm.O1_2024_12_17, Llm.GPT_5_MINI):
    params["temperature"] = 0
    params["stream"] = True

# Thêm max_completion_tokens cho GPT-5-mini (khoảng dòng 94)
if model == Llm.GPT_5_MINI:
    params["max_completion_tokens"] = 16384

# Sửa non-streaming logic (khoảng dòng 101)
if model in (Llm.O1_2024_12_17, Llm.GPT_5_MINI):
    response = await client.chat.completions.create(**params)  # type: ignore
    full_response = response.choices[0].message.content  # type: ignore
    await callback(full_response)  # ← Thêm callback để gửi response
else:
    # streaming logic for other models
```

### 3. Cập nhật Routing Logic

**File**: `backend/routes/generate_code.py`

```python
# Thay đổi default models từ GPT-4o sang GPT-5-mini (khoảng dòng 270-272)
if openai_api_key and anthropic_api_key:
    variant_models = [claude_model, Llm.GPT_5_MINI]  # ← Thay GPT_4O_2024_11_20
elif openai_api_key or azure_openai_available:
    variant_models = [Llm.GPT_5_MINI, Llm.GPT_5_MINI]  # ← Thay GPT_4O_2024_11_20

# Thêm GPT_5_MINI vào điều kiện xử lý OpenAI models (khoảng dòng 283)
if model in (Llm.GPT_4O_2024_11_20, Llm.GPT_5_MINI, Llm.O1_2024_12_17):
    # Azure OpenAI logic...
```

## 📋 Checklist Triển Khai

Khi clone dự án và muốn setup Azure OpenAI + GPT-5-mini:

### Bước 1: Environment Setup
- [ ] Tạo file `backend/.env` với Azure OpenAI credentials
- [ ] Đảm bảo Azure deployment name khớp với `AZURE_OPENAI_DEPLOYMENT_NAME`
- [ ] Kiểm tra API version compatibility

### Bước 2: Code Changes
- [ ] Thêm `GPT_5_MINI = "gpt-5-mini"` vào `backend/llm.py`
- [ ] Cập nhật validation logic trong `backend/routes/generate_code.py`
- [ ] Cấu hình model parameters cho GPT-5-mini (non-streaming, max_completion_tokens)
- [ ] Cập nhật routing logic để sử dụng GPT-5-mini

### Bước 3: Testing
- [ ] Chạy backend: `cd backend && poetry run uvicorn main:app --reload --port 7001`
- [ ] Kiểm tra logs không có lỗi API key validation
- [ ] Test upload ảnh và generate code
- [ ] Verify response từ GPT-5-mini

## 🐛 Common Issues & Solutions

### Issue 1: "No OpenAI or Anthropic API key found"
**Nguyên nhân**: Validation logic chưa nhận diện Azure OpenAI
**Giải pháp**: Thêm `azure_openai_available` check vào validation

### Issue 2: "max_tokens is not supported with this model"
**Nguyên nhân**: GPT-5-mini không hỗ trợ `max_tokens`
**Giải pháp**: Dùng `max_completion_tokens` thay thế

### Issue 3: Streaming errors với GPT-5-mini
**Nguyên nhân**: GPT-5-mini không hỗ trợ streaming
**Giải pháp**: Treat như O1 model (non-streaming)

### Issue 4: Temperature errors
**Nguyên nhân**: GPT-5-mini không hỗ trợ temperature parameter
**Giải pháp**: Exclude khỏi temperature setting

## 📚 References

- [Azure OpenAI Service Documentation](https://docs.microsoft.com/en-us/azure/cognitive-services/openai/)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Screenshot-to-Code Project](https://github.com/abi/screenshot-to-code)

---

**Created**: 2025-09-28
**Author**: Claude Code Assistant
**Project**: Screenshot-to-Code Azure OpenAI Integration
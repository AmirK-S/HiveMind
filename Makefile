.PHONY: generate-sdks generate-openapi generate-python-sdk generate-ts-sdk check-sdk-drift

# Export the OpenAPI spec from the FastAPI app (no running server required)
generate-openapi:
	.venv/bin/python scripts/export_openapi.py

# Generate Python SDK from spec using openapi-python-client
generate-python-sdk: generate-openapi
	.venv/bin/openapi-python-client generate \
	  --path openapi.json \
	  --output-path sdks/python \
	  --overwrite

# Generate TypeScript SDK from spec using @hey-api/openapi-ts
generate-ts-sdk: generate-openapi
	npx @hey-api/openapi-ts \
	  -i openapi.json \
	  -o sdks/typescript/src/client \
	  --plugins @hey-api/typescript @hey-api/sdk

# Regenerate both SDKs from the current OpenAPI spec
generate-sdks: generate-python-sdk generate-ts-sdk
	@echo "SDKs generated successfully"

# CI drift check — fails if generated code differs from committed SDKs
# Run this in CI to ensure committed SDK code matches the current server spec
check-sdk-drift: generate-sdks
	git diff --exit-code sdks/ || (echo "SDK drift detected! Run 'make generate-sdks' and commit the result." && exit 1)

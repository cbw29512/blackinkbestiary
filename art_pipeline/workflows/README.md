# Workflow Slot

`flux2_klein_api.json` will contain the approved **API-format** ComfyUI workflow for FLUX.2 [klein] 4B.

Do not paste a normal UI workflow here and assume it is compatible.

The production workflow must:
1. use the approved local FLUX.2 Klein model,
2. produce portrait PNG output,
3. save the final image through a normal ComfyUI image output node,
4. contain `__BLACKINK_PROMPT__` in the prompt field,
5. contain `__BLACKINK_SEED__` in the seed field.

The worker validates both required tokens before allowing generation.

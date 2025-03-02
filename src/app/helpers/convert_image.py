import base64
# Forma de importar este modulo app.helpers.convert_image import convert_image_to_base64

def convert_image_to_base64(image_path):
    try:
        with open(image_path, "rb") as image_file:
            # Codificar la imagen en base64
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            return base64_image
    except Exception as e:
        # Corregir la sintaxis del return
        return f'Error: {str(e)}'
    


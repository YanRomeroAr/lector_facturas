import streamlit as st
import requests
import json
from PIL import Image
import io
import time
import re
import pandas as pd

# Configuración de página
st.set_page_config(
    page_title="🧾 Extractor de Datos de Facturas",
    page_icon="📊",
    layout="wide"
)

# CSS personalizado
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    .success-box {
        background: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Header principal
st.markdown("""
<div class="main-header">
    <h1>🧾 Extractor Inteligente de Datos de Facturas</h1>
    <p>Extrae automáticamente información de facturas usando Azure Computer Vision OCR</p>
</div>
""", unsafe_allow_html=True)

# Configuración Azure
AZURE_ENDPOINT = st.secrets.get("AZURE_ENDPOINT", "")
AZURE_API_KEY = st.secrets.get("AZURE_API_KEY", "")

def extract_text_from_image(image_data):
    """Extrae texto de imagen usando Azure Computer Vision OCR"""
    if not AZURE_ENDPOINT or not AZURE_API_KEY:
        st.error("❌ Credenciales de Azure no configuradas")
        return None
    
    # URL para OCR
    ocr_url = f"{AZURE_ENDPOINT}/vision/v3.2/read/analyze"
    
    headers = {
        'Ocp-Apim-Subscription-Key': AZURE_API_KEY,
        'Content-Type': 'application/octet-stream'
    }
    
    try:
        # Iniciar análisis OCR
        response = requests.post(ocr_url, headers=headers, data=image_data)
        response.raise_for_status()
        
        # Obtener URL del resultado
        operation_url = response.headers["Operation-Location"]
        
        # Esperar a que se complete el análisis
        analysis_complete = False
        while not analysis_complete:
            time.sleep(1)
            result_response = requests.get(operation_url, headers=headers)
            result_response.raise_for_status()
            result = result_response.json()
            
            if result["status"] == "succeeded":
                analysis_complete = True
            elif result["status"] == "failed":
                st.error("❌ Error en el análisis OCR")
                return None
        
        return result["analyzeResult"]
    
    except requests.exceptions.RequestException as e:
        st.error(f"❌ Error al procesar imagen: {str(e)}")
        return None

def extract_invoice_data(ocr_result):
    """Extrae datos específicos de factura del texto OCR"""
    if not ocr_result or "readResults" not in ocr_result:
        return {}
    
    # Concatenar todo el texto
    full_text = ""
    for page in ocr_result["readResults"]:
        for line in page["lines"]:
            full_text += line["text"] + "\n"
    
    # Diccionario para almacenar datos extraídos
    invoice_data = {
        "numero_factura": "",
        "fecha": "",
        "empresa": "",
        "ruc_nit": "",
        "cliente": "",
        "total": "",
        "subtotal": "",
        "igv_iva": "",
        "items": []
    }
    
    # Patrones de búsqueda
    patterns = {
        "numero_factura": [
            r"(?:factura|invoice|n[úu]mero?)[:\s#]*([A-Z0-9\-]+)",
            r"(?:fact|fac)[:\s#]*([A-Z0-9\-]+)",
            r"(?:serie|no\.?)[:\s]*([A-Z0-9\-]+)"
        ],
        "fecha": [
            r"(?:fecha|date)[:\s]*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})",
            r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})"
        ],
        "ruc_nit": [
            r"(?:ruc|nit|tax\s*id)[:\s]*(\d{10,15})",
            r"(\d{11})"  # RUC típico de 11 dígitos
        ],
        "total": [
            r"(?:total|amount)[:\s]*[S\/\$]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})",
            r"(?:total\s*general|grand\s*total)[:\s]*[S\/\$]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})"
        ],
        "subtotal": [
            r"(?:subtotal|sub\s*total)[:\s]*[S\/\$]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})"
        ],
        "igv_iva": [
            r"(?:igv|iva|tax)[:\s]*[S\/\$]?\s*(\d{1,3}(?:,\d{3})*\.?\d{0,2})"
        ]
    }
    
    # Buscar cada patrón
    for field, field_patterns in patterns.items():
        for pattern in field_patterns:
            match = re.search(pattern, full_text, re.IGNORECASE)
            if match and not invoice_data[field]:
                invoice_data[field] = match.group(1).strip()
                break
    
    # Extraer nombre de empresa (primeras líneas)
    lines = full_text.split('\n')
    for i, line in enumerate(lines[:5]):
        if len(line.strip()) > 5 and not re.search(r'\d', line):
            invoice_data["empresa"] = line.strip()
            break
    
    # Buscar items de productos (líneas con precio)
    for line in lines:
        if re.search(r'\d+[\.\,]\d{2}', line) and len(line.split()) >= 3:
            invoice_data["items"].append(line.strip())
    
    return invoice_data, full_text

def display_invoice_data(invoice_data, full_text):
    """Muestra los datos extraídos de manera organizada"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📊 Datos Principales")
        
        # Métricas principales
        if invoice_data["numero_factura"]:
            st.metric("🔢 Número de Factura", invoice_data["numero_factura"])
        
        if invoice_data["fecha"]:
            st.metric("📅 Fecha", invoice_data["fecha"])
        
        if invoice_data["total"]:
            st.metric("💰 Total", f"S/ {invoice_data['total']}")
        
        # Información adicional
        st.markdown("### 🏢 Información de Empresa")
        if invoice_data["empresa"]:
            st.write(f"**Empresa:** {invoice_data['empresa']}")
        if invoice_data["ruc_nit"]:
            st.write(f"**RUC/NIT:** {invoice_data['ruc_nit']}")
    
    with col2:
        st.subheader("💵 Desglose Financiero")
        
        if invoice_data["subtotal"]:
            st.write(f"**Subtotal:** S/ {invoice_data['subtotal']}")
        
        if invoice_data["igv_iva"]:
            st.write(f"**IGV/IVA:** S/ {invoice_data['igv_iva']}")
        
        if invoice_data["total"]:
            st.write(f"**Total:** S/ {invoice_data['total']}")
        
        # Items encontrados
        if invoice_data["items"]:
            st.markdown("### 🛍️ Items Detectados")
            for i, item in enumerate(invoice_data["items"][:5], 1):
                st.write(f"{i}. {item}")
    
    # Crear tabla resumen
    st.subheader("📋 Resumen Extraído")
    
    data_summary = []
    for key, value in invoice_data.items():
        if key != "items" and value:
            data_summary.append({"Campo": key.replace("_", " ").title(), "Valor": value})
    
    if data_summary:
        df = pd.DataFrame(data_summary)
        st.dataframe(df, use_container_width=True)
    
    # Mostrar texto completo extraído
    with st.expander("📄 Ver texto completo extraído"):
        st.text_area("Texto OCR completo:", full_text, height=200)

# Interfaz principal
st.markdown("### 📤 Sube una imagen de factura")

uploaded_file = st.file_uploader(
    "Selecciona una imagen de factura (JPG, PNG, PDF)",
    type=['jpg', 'jpeg', 'png', 'pdf'],
    help="Sube una imagen clara de la factura para extraer los datos automáticamente"
)

if uploaded_file is not None:
    # Mostrar imagen
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("🖼️ Factura Original")
        
        try:
            image = Image.open(uploaded_file)
            st.image(image, caption="Factura subida", use_column_width=True)
            
            # Convertir a bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
        except Exception as e:
            st.error(f"Error al procesar imagen: {str(e)}")
            img_byte_arr = None
    
    with col2:
        if img_byte_arr and st.button("🔍 Extraer Datos de Factura", type="primary", use_container_width=True):
            
            with st.spinner("🔄 Procesando factura con Azure OCR..."):
                # Extraer texto
                ocr_result = extract_text_from_image(img_byte_arr)
                
                if ocr_result:
                    # Procesar datos de factura
                    invoice_data, full_text = extract_invoice_data(ocr_result)
                    
                    st.success("✅ ¡Datos extraídos exitosamente!")
                    
                    # Mostrar resultados
                    st.markdown("---")
                    display_invoice_data(invoice_data, full_text)
                    
                    # Botón para descargar datos
                    if invoice_data:
                        json_data = json.dumps(invoice_data, indent=2, ensure_ascii=False)
                        st.download_button(
                            label="💾 Descargar datos JSON",
                            data=json_data,
                            file_name="datos_factura.json",
                            mime="application/json"
                        )

# Información sobre la app
st.markdown("---")
st.markdown("### ℹ️ Características de la Aplicación")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **🔍 Extracción Automática:**
    - Número de factura
    - Fecha de emisión
    - RUC/NIT de empresa
    - Información del cliente
    """)

with col2:
    st.markdown("""
    **💰 Datos Financieros:**
    - Total de la factura
    - Subtotal
    - IGV/IVA
    - Items de productos
    """)

with col3:
    st.markdown("""
    **📊 Funcionalidades:**
    - OCR con Azure Computer Vision
    - Exportación en JSON
    - Interfaz intuitiva
    - Procesamiento en tiempo real
    """)

# Sidebar con instrucciones
st.sidebar.title("📋 Guía de Uso")
st.sidebar.markdown("""
### 🚀 Pasos para usar:

1. **Subir factura:** Arrastra o selecciona imagen
2. **Procesar:** Clic en "Extraer Datos"
3. **Revisar:** Verifica datos extraídos
4. **Descargar:** Exporta en JSON

### 📝 Tipos de datos extraídos:
- 🔢 Número de factura
- 📅 Fecha
- 🏢 Empresa emisora
- 🆔 RUC/NIT
- 💰 Montos (total, subtotal, IGV)
- 🛍️ Items de productos

### 💡 Consejos:
- Usa imágenes de buena calidad
- Asegúrate de que el texto sea legible
- Formatos soportados: JPG, PNG, PDF
""")

st.sidebar.markdown("---")
st.sidebar.info("**Powered by:** Azure Computer Vision OCR + Streamlit")

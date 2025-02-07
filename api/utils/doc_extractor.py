import base64
import logging
from api.exceptions import FileProcessingError
from api.utils.docling_doc_converter import convert_pdf_bytes_to_text, convert_word_bytes_to_text

logger = logging.getLogger(__name__)

def extract_text(data: dict) -> str:
    """Extrai o texto de um documento codificado em base64 utilizando o docling.

    Args:
        data (dict): Dicionário com os seguintes itens:
            - name (str): Nome do arquivo (para identificar a extensão);
            - content (str): Conteúdo do arquivo em base64.

    Returns:
        str: Texto extraído do documento.

    Raises:
        FileProcessingError: Se os dados estiverem incompletos ou ocorrer erro na conversão.
    """
    function_name = 'extract_text'
    if not data:
        logger.error(f"{function_name}: Nenhum dado de instrução fornecido.")
        raise FileProcessingError("Nenhum dado de instrução fornecido.")
    
    name = data.get('name')
    content = data.get('content')
    if not name or not content:
        logger.error(f"{function_name}: Dados de instrução incompletos.")
        raise FileProcessingError("Dados de instrução incompletos.")

    try:
        file_bytes = base64.b64decode(content)
        logger.debug(f"{function_name}: Conteúdo do arquivo decodificado com sucesso.")
    except Exception as e:
        logger.error(f"{function_name}: Erro ao decodificar o conteúdo do arquivo: {e}")
        raise FileProcessingError(f"Erro ao decodificar o conteúdo do arquivo: {e}")

    try:
        lower_name = name.lower()
        if lower_name.endswith('.pdf'):
            text = convert_pdf_bytes_to_text(file_bytes, name)
        elif lower_name.endswith('.docx'):
            text = convert_word_bytes_to_text(file_bytes, name)
        else:
            raise FileProcessingError("Formato de arquivo não suportado para conversão com docling.")
        
        logger.info(f"{function_name}: Texto extraído com sucesso.")
        return text
    except Exception as e:
        logger.error(f"{function_name}: Erro ao processar o documento: {e}")
        raise FileProcessingError(f"Erro ao processar o documento: {e}")

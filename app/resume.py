"""Text PDF preview: no file storage, OCR, grades or automatic publication."""
import io
import json
import re
import subprocess
import sys
from pathlib import Path

MAX_PDF_BYTES=2*1024*1024
SKILLS=['Python','FastAPI','Django','Flask','SQL','PostgreSQL','Docker','JavaScript','TypeScript','React','Vue','CSS','HTML','HTTP']


def extract_fields(content):
    from pypdf import PdfReader
    from pypdf import filters
    filters.ZLIB_MAX_OUTPUT_LENGTH=5*1024*1024
    if not content.startswith(b'%PDF-'):raise ValueError('Файл не является PDF')
    reader=PdfReader(io.BytesIO(content),strict=True)
    if reader.is_encrypted:raise ValueError('Снимите пароль с PDF перед загрузкой')
    if len(reader.pages)>10:raise ValueError('В резюме должно быть не больше 10 страниц')
    pages=[]
    for page in reader.pages:
        stream=page.get_contents()
        if stream is not None and len(stream.get_data())>5*1024*1024:raise ValueError('Слишком сложный PDF')
        pages.append(page.extract_text() or '')
    text='\n'.join(pages)
    if not text.strip():raise ValueError('В PDF нет текстового слоя. Используйте текстовый PDF или заполните анкету вручную')
    # ponytail: allowlisted skills and explicit field labels; add OCR/NLP only with a validated corpus.
    suggestions={'skills':[skill for skill in SKILLS if re.search(r'(?<!\w)'+re.escape(skill)+r'(?!\w)',text,re.I)]}
    name=re.search(r'^(?:ФИО|Имя и фамилия|Имя)\s*[:—]\s*([^\n]{2,100})$',text,re.M|re.I)
    if name:suggestions['name']=name.group(1).strip()
    phone=re.search(r'(?<!\w)(?:\+7|8)[ (.-]*\d{3}[ ).-]*\d{3}[ .-]*\d{2}[ .-]*\d{2}(?!\d)',text)
    if phone:suggestions['phone']=phone.group(0)
    telegram=re.search(r'(?:Telegram\s*[:—]?\s*@|(?:https?://)?t\.me/)([A-Za-z0-9_]{5,32})\b',text,re.I)
    if telegram:suggestions['telegram']='@'+telegram.group(1)
    experience=re.search(r'опыт(?:\s+работы)?\s*[:—]?\s*(\d{1,2})\s*(?:лет|год(?:а)?)\b',text,re.I)
    if experience and int(experience.group(1))<=60:suggestions['experience']=int(experience.group(1))
    return suggestions


def parse_resume(content):
    if len(content)>MAX_PDF_BYTES:raise ValueError('PDF должен быть не больше 2 МБ')
    if not content.startswith(b'%PDF-'):raise ValueError('Файл не является PDF')
    try:
        result=subprocess.run([sys.executable,str(Path(__file__).resolve())],input=content,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=8,check=False)
        if result.returncode:raise ValueError('Не удалось прочитать PDF. Используйте текстовый PDF без пароля')
        data=json.loads(result.stdout)
        if 'error' in data:raise ValueError(data['error'])
        return data
    except (subprocess.TimeoutExpired,json.JSONDecodeError,OSError):raise ValueError('Не удалось прочитать PDF за 8 секунд. Используйте более простой текстовый PDF')


if __name__=='__main__':
    if sys.platform.startswith('linux'):
        import resource
        resource.setrlimit(resource.RLIMIT_AS,(512*1024*1024,512*1024*1024))
        resource.setrlimit(resource.RLIMIT_CPU,(6,6))
    try:
        content=sys.stdin.buffer.read(MAX_PDF_BYTES+1)
        if len(content)>MAX_PDF_BYTES:raise ValueError('PDF должен быть не больше 2 МБ')
        result=extract_fields(content)
    except ValueError as error:result={'error':str(error)}
    except Exception:result={'error':'Не удалось прочитать PDF. Используйте текстовый PDF без пароля'}
    print(json.dumps(result,ensure_ascii=True))

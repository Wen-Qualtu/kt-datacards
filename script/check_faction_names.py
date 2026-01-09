import fitz

pdf = fitz.open('input/ravener/ravener-faction-rules.pdf')

for i in range(min(5, len(pdf))):
    page = pdf[i]
    text_dict = page.get_text('dict')
    
    text_by_size = []
    for block in text_dict['blocks']:
        if block['type'] == 0:
            for line in block['lines']:
                for span in line['spans']:
                    text = span['text'].strip()
                    if text:
                        text_by_size.append((span['size'], text))
    
    text_by_size.sort(reverse=True, key=lambda x: x[0])
    
    print(f'\n=== Page {i+1} ===')
    for size, text in text_by_size[:10]:
        print(f'{size:.1f}: {text[:60]}')

pdf.close()

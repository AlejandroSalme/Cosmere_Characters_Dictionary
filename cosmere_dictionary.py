import time
import os
import json
import questionary
import shutil
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# URL of the page to scrape
TIME_MACHINE_URL = 'https://es.coppermind.net/wiki/Especial:M%C3%A1quinaDelTiempo'
CATEGORY_URL = 'https://es.coppermind.net/wiki/Categor%C3%ADa:De_'

def fetch_character_data(driver, category_url):
    driver.get(category_url)

    # Get the page source after JavaScript has rendered
    soup = BeautifulSoup(driver.page_source, 'html.parser')

    # Find the section that starts with the <h2> with the exact text
    category = category_url.split(':')[2].replace('_', ' ')
    print(f'Category: {category}')
    section = soup.find('h2', string=f'Páginas en la categoría «{category}»')
    
    # If the section is found, get the following sibling, which contains the list of characters
    character_names = []

    if section:
        # Find all <div class='mw-category-group'> to extract character names
        all_content = section.find_next('div', class_='mw-content-ltr')
        
        # Find all <a> tags with a title attribute
        links = all_content.find_all('a', title=True)

        # Extract and print the title attributes
        character_names = [link['title'] for link in links]

    character_dict = {}

    for name in character_names:
        print(name + '\n')

        # Fetch character page using Selenium
        driver.get(f'https://es.coppermind.net/w/api.php?action=query&format=json&titles={name}&prop=extracts&exintro=True&explaintext=True')
        time.sleep(3)  # Allow time for page to load
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        data = soup.find('pre').text

        try:
            # Parse the JSON text
            json_data = json.loads(data)

            if 'query' in json_data and 'pages' in json_data['query']:
                pages = json_data['query']['pages']
                for page_id, page_info in pages.items():
                    if 'extract' in page_info:
                        description = page_info['extract']
                        character_dict[name] = description
                        break  # Stop once the extract is found
            else:
                print('No valid data found in the response.')
        except json.JSONDecodeError:
            print('Failed to decode JSON from the response.')
    
    return character_dict

def create_xhtml(character_dict):
    '''Create XHTML content for the Kindle dictionary.'''
    entries = []
    for name, description in character_dict.items():
        name_split = name.split(' ')[0]
        entry = f'''
        <idx:entry name='entry' scriptable='yes' spell='yes'>
            <idx:orth value='{name_split}'><b>{name}</b>
                <idx:infl>
                    <idx:iform value='{name}'></idx:iform>
                </idx:infl>
            </idx:orth>
            <p> {description} </p>
        </idx:entry>
        '''
        entries.append(entry)

    content = f'''
    <html xmlns:math='http://exslt.org/math' 
      xmlns:svg='http://www.w3.org/2000/svg' 
      xmlns:tl='https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf'
      xmlns:saxon='http://saxon.sf.net/' 
      xmlns:xs='http://www.w3.org/2001/XMLSchema' 
      xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance'
      xmlns:cx='https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf' 
      xmlns:dc='http://purl.org/dc/elements/1.1/'
      xmlns:mbp='https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf' 
      xmlns:mmc='https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf' 
      xmlns:idx='https://kindlegen.s3.amazonaws.com/AmazonKindlePublishingGuidelines.pdf'>

    <head>
        <meta http-equiv='Content-Type' content='text/html; charset=utf-8'>
    </head>

    <body>
        <mbp:frameset>
            {''.join(entries)}
        </mbp:frameset>
    </body>

    </html>
    '''
    return content

def create_opf(planet):
    '''Create OPF package file for the Kindle dictionary.'''
    opf_content = f'''
    <?xml version='1.0' encoding='UTF-8'?>
    <package xmlns='http://www.idpf.org/2007/opf' unique-identifier='uid'>
      <metadata>
        <dc:title>Personajes de {planet}</dc:title>
        <dc:language>es</dc:language>
        <dc:identifier id='uid'>{planet}-dictionary</dc:identifier>
        <meta name='cover' content='cover-image'/>
        <x-metadata>
        <DictionaryInLanguage>es</DictionaryInLanguage>
        <DictionaryOutLanguage>es</DictionaryOutLanguage>
        <DefaultLookupIndex>headword</DefaultLookupIndex>
        </x-metadata>
      </metadata>
      <manifest>
        <item id='content' href='content.xhtml' media-type='application/xhtml+xml'/>
        <item id='css' href='style.css' media-type='text/css'/>
        <item id='cover' href='{planet}_cover.jpg' media-type='image/jpeg'/>
      </manifest>
      <spine>
        <itemref idref='content'/>
      </spine>
    </package>
    '''
    return opf_content

def create_css():
    '''Create CSS file for the Kindle dictionary.'''
    css_content = '''
    body {
        font-family: Arial, sans-serif;
        line-height: 1.6;
    }
    idx\\:entry {
        margin: 10px 0;
    }
    definition {
        color: #333;
    }
    '''
    return css_content

def save_files(character_dict, planet):
    '''Save files for Kindle dictionary generation.'''
    os.makedirs(f'{planet}_dictionary', exist_ok=True)

    # Save XHTML content
    with open(f'{planet}_dictionary/content.xhtml', 'w', encoding='utf-8') as f:
        f.write(create_xhtml(character_dict))

    # Save OPF package
    with open(f'{planet}_dictionary/{planet}_dictionary.opf', 'w', encoding='utf-8') as f:
        f.write(create_opf(planet))

    # Save CSS
    with open(f'{planet}_dictionary/style.css', 'w', encoding='utf-8') as f:
        f.write(create_css())

    # Save cover image (placeholder)
    cover_file=f'./covers/{planet}_cover.jpg'
    template_file='./covers/template_cover.jpg'
    shutil.copy(cover_file, f'{planet}_dictionary') if os.path.exists(cover_file) else shutil.copy(template_file, f'{planet}_dictionary')

def main():
    '''Main function to scrape data and generate Kindle dictionary.'''
    try:
        # Books options
        books_planet = {
            'Nacidos de la bruma': 'Scadrial',
            'El archivo de las tormentas': 'Roshar',
            'Elantris / El alma del emperador': 'Sel',
            'El aliento de los dioses': 'Nalthis',
            'Sombras por Silencio en los bosques del infierno': 'Treno',
            'Sexto del Ocaso': 'las_islas_Eelakin',
            'Arena Blanca': 'Taldain',
            'El Hombre Iluminado (WIP)': 'Cantico',
            'Trenza del mar Esmeralda': 'Lumar',
            'Yumi y el pintor de pesadillas': 'Komashi',
            'Planeta': ''
        }

        # Ask the user to select options
        selected = questionary.checkbox(
            'Select the books you are interested in (use Space to select, Enter to confirm):',
            choices=list(books_planet.keys())
        ).ask()

        # Process the selection
        if selected:
            if 'Planeta' in selected:
                planets_stdin = questionary.text('Enter the planet name with first character in uppercase:').ask()
                books_planet.update({'Planeta': planets_stdin})
        
        '''Fetch character names and descriptions from the given URL using Selenium'''
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        driver.get(TIME_MACHINE_URL)
        
        # Wait for the page to load completely
        time.sleep(10)

        for selection in selected:
            planet = books_planet.get(selection)

            print(f'Fetching characters data from book {selection}')
            character_dict = fetch_character_data(driver, CATEGORY_URL + planet)

            if not character_dict:
                break
            
            print(f'Creating dictionary files...')
            save_files(character_dict, planet) if planet != 'las_islas_Eelakin' else save_files(character_dict, planet.split('_')[2])

            print(f'Kindle dictionary files saved in {planet}_dictionary folder.')

        driver.quit()  # Close the WebDriver
        
    except Exception as e:
        print(f'An error occurred: {e}')

if __name__ == '__main__':
    main()

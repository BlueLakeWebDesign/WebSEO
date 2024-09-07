import os
import openai
import random
from google.cloud import vision
from PIL import Image
import piexif
import subprocess
from tkinter import filedialog
from tkinter import Tk

# OpenAI API key
openai.api_key = '[YOUR API KEY]'

# Google Cloud Vision client setup
def get_vision_client():
    return vision.ImageAnnotatorClient()

def analyze_image(image_path):
    """Uses Google Cloud Vision API to analyze an image and prioritize objects by their estimated size."""
    client = get_vision_client()
    with open(image_path, 'rb') as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    # Use object localization to get objects and their bounding polygons
    response = client.object_localization(image=image).localized_object_annotations

    objects_with_areas = []

    for object_annotation in response:
        # Each object_annotation has a bounding_poly
        vertices = object_annotation.bounding_poly.normalized_vertices
        # Assuming a rectangular bounding box, calculate area
        # Note: This simplistic approach assumes the bounding box is a rectangle
        # which might not always be the case, but it's a reasonable approximation for this purpose.
        if len(vertices) >= 4:  # Ensure there are enough points to calculate area
            width = abs(vertices[1].x - vertices[0].x)
            height = abs(vertices[2].y - vertices[1].y)
            area = width * height
            objects_with_areas.append((object_annotation.name, area))

    # Sort objects by area, largest first
    objects_with_areas.sort(key=lambda x: x[1], reverse=True)

    # Generate description based on sorted objects
    description = ', '.join([obj[0] for obj in objects_with_areas])
    return description

def get_extended_description(short_description):
    try:
        prompt = f"Describe the elements in this photo clearly and confidently, avoiding phrases like 'appears to be'. Use definitive language: {short_description}"
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a professional website designer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=60,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        print("Error in generating extended description:", e)
        return short_description

def create_title(description):
    words = description.split(', ')
    # Ensure the list is unique and shuffled
    unique_words = list(set(words))
    random.shuffle(unique_words)
    
    # Select 1-5 words randomly
    num_words = random.randint(1, min(5, len(unique_words)))
    title_words = unique_words[:num_words]
    
    # Join the selected words into a title
    title = ' '.join(word.capitalize() for word in title_words)
    return title[:177] + "..." if len(title) > 180 else title

def edit_image_metadata(image_path, initial_description, extended_description, save_folder):
    title = create_title(initial_description)
    headline = "Headline: " + title

    exif_dict = {
        '0th': {
            piexif.ImageIFD.ImageDescription: extended_description.encode('utf-8'),
        },
        'Exif': {},
        '1st': {},
        'thumbnail': None,
    }

    exif_bytes = piexif.dump(exif_dict)

    base_name = os.path.basename(image_path)
    new_path = os.path.join(save_folder, "edited_" + base_name)
    img = Image.open(image_path)
    img.save(new_path, "JPEG", exif=exif_bytes)

    subprocess.run(['exiftool', '-XMP-dc:description=' + extended_description, '-XMP-dc:title=' + title, '-XMP-photoshop:Headline=' + headline, new_path], stdout=subprocess.DEVNULL)

def select_folder():
    root = Tk()
    root.withdraw()
    folder_selected = filedialog.askdirectory()
    root.destroy()
    return folder_selected

def main():
    folder_path = select_folder()
    if not folder_path:
        print("No folder selected. Exiting.")
        return

    save_folder = os.path.join(folder_path, "EditedImages")
    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(('.jpg', '.jpeg')):
            image_path = os.path.join(folder_path, filename)
            try:
                initial_description = analyze_image(image_path)
                extended_description = get_extended_description(initial_description)
                edit_image_metadata(image_path, initial_description, extended_description, save_folder)
                print(f"Processed {filename}")
            except Exception as e:
                print(f"Error processing {filename}: {e}")

if __name__ == "__main__":
    main()

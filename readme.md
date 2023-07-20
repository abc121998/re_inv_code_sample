**This is an modified version of the UMBC Retriever's Essentials Pantry Inventory App intended for job application purposes**

While the original is a web application that uses the Django Framework, Heroku, and a postgreSQL database, this one is
a single file that creates a dataframe for current inventory each time it runs. The project also contains a pickled model for automatic categorization and a small csv file of about 110 products from an USDA Database. 

Allows User to:

    1. Add Products and update their quantities
    2. Predicts Product SWAP categories and determines SWAP grade (user can confirm SWAP categories)
    3. Mass update inventory through a csv file
    4. Search for Products
    5. View HTML Inventory Table
    6. Display Visualizations
    7. Write inventory csv files
    
To download needed modules simply type pip install -r requirements.txt in the command line before running program.

Author: Abbey Cotton
e-mail: abig3@umbc.edu

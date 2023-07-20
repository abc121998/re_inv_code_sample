import pandas as pd
import requests
import pickle, os, re, string, webbrowser, csv
from checkdigit import gs1
import plotly.graph_objects as go
from plotly.subplots import make_subplots

#groups
categories = ["FR","VEG","GR","DA","MXD","ANML_PRO","PLT_PRO","SK","DES","CON","BEV","U"]
cat_abbrev = {"FR":'Fruits',"VEG":'Vegetables',"GR":'Grains',"DA":'Dairy',"MXD":'Mixed',"ANML_PRO":'Animal Protein',
              "PLT_PRO":'Plant Protein',"SK":'Snacks',"DES":'Desserts',"CON":'Condiments',"BEV":'Beverage',"U":'Unknown'}
swap_grades = {'U':'Unranked','R':'Red','Y':'Yellow','G':'Green',}
nutri_grades = ['E','D','C','B','A']

#category colors
cat_colors = ["rgb(72,191,142)", "rgb(67,42,183)", "rgb(173,230,79)", "rgb(47,91,177)", "rgb(237,177,255)",
              "rgb(11,82,46)", "rgb(161,222,240)", "rgb(108,57,32)", "rgb(76,243,44)", "rgb(224,87,225)",
              "rgb(75,164,11)", "rgb(251,32,118)"]
nutri_colors = ['#d7191c','#fdae61','#ffffbf','#a6d96a','#1a9641']
COLOR_MAPPING = {"all":"rgb(37,102,118)","R":"rgb(252,3,3)","Y":"rgb(252,227,3)","G":"rgb(4,209,4)","U":"#bababa"}
for cat in categories:
    COLOR_MAPPING[cat] = cat_colors[categories.index(cat)]
for i in range(len(nutri_grades)):
    COLOR_MAPPING[nutri_grades[i]] = nutri_colors[i]
COLOR_MAPPING['UNKNOWN'] = '#bababa'
COLOR_MAPPING['NOT-APPLICABLE'] = '#bababa'
COLOR_MAPPING['NA'] = '#bababa'

#Information required for SWAP categorization
swap_classification = {}
for cat in categories:
    for nutrient in ['saturated_fat','sodium','sugars']:
        swap_classification[cat] = {nutrient:{'Green':0,'Yellow':0,'Red':0}}

swap_classification["ANML_PRO"]["saturated_fat"] = {'Green': 2, 'Yellow': 5, 'Red': 5.5}
swap_classification["ANML_PRO"]["sodium"] = {'Green': 200, 'Yellow': 480, 'Red': 481}
swap_classification["ANML_PRO"]["sugars"] = {'Green': 0, 'Yellow': 1, 'Red': 2}

swap_classification["BEV"]["saturated_fat"] = {'Green': 0, 'Yellow': 0, 'Red': 0}
swap_classification["BEV"]["sodium"] = {'Green': 0, 'Yellow': 160, 'Red': 161}
swap_classification["BEV"]["sugars"] = {'Green': 0, 'Yellow': 11, 'Red': 12}

swap_classification["CON"]["saturated_fat"] = {'Green': 0, 'Yellow': 0.5, 'Red': 1}
swap_classification["CON"]["sodium"] = {'Green': 250, 'Yellow': 350, 'Red': 351}
swap_classification["CON"]["sugars"] = {'Green': 2, 'Yellow': 7, 'Red': 8}

swap_classification["DA"]["saturated_fat"] = {'Green': 1.5, 'Yellow': 3, 'Red': 3.5}
swap_classification["DA"]["sodium"] = {'Green': 180, 'Yellow': 200, 'Red': 201}
swap_classification["DA"]["sugars"] = {'Green': 12, 'Yellow': 22, 'Red': 23}

swap_classification["DES"]["saturated_fat"] = {'Green': 2, 'Yellow': 2, 'Red': 2.5}
swap_classification["DES"]["sodium"] = {'Green': 230, 'Yellow': 400, 'Red': 401}
swap_classification["DES"]["sugars"] = {'Green': 6, 'Yellow': 12, 'Red': 13}

swap_classification["FR"]["saturated_fat"] = {'Green':1,'Yellow':1,'Red':1.5}
swap_classification["FR"]["sodium"] = {'Green':32,'Yellow':50,'Red':51}
swap_classification["FR"]["sugars"] = {'Green':12,'Yellow':25,'Red':26}

swap_classification["GR"]["saturated_fat"] = {'Green': 2, 'Yellow': 2, 'Red': 2.5}
swap_classification["GR"]["sodium"] = {'Green': 230, 'Yellow': 400, 'Red': 401}
swap_classification["GR"]["sugars"] = {'Green': 6, 'Yellow': 12, 'Red': 13}

swap_classification["MXD"]["saturated_fat"] = {'Green': 3, 'Yellow': 6, 'Red': 6.5}
swap_classification["MXD"]["sodium"] = {'Green': 480, 'Yellow': 600, 'Red': 600}
swap_classification["MXD"]["sugars"] = {'Green': 7, 'Yellow': 10, 'Red': 10}

swap_classification["PLT_PRO"]["saturated_fat"] = {'Green': 2, 'Yellow': 5, 'Red': 5.5}
swap_classification["PLT_PRO"]["sodium"] = {'Green': 230, 'Yellow': 480, 'Red': 481}
swap_classification["PLT_PRO"]["sugars"] = {'Green': 5, 'Yellow': 9, 'Red': 10}

swap_classification["SK"]["saturated_fat"] = {'Green': 2, 'Yellow': 2, 'Red': 2.5}
swap_classification["SK"]["sodium"] = {'Green': 230, 'Yellow': 400, 'Red': 401}
swap_classification["SK"]["sugars"] = {'Green': 6, 'Yellow': 12, 'Red': 13}

swap_classification["VEG"]["saturated_fat"] = {'Green':1,'Yellow':1,'Red':1.5}
swap_classification["VEG"]["sodium"] = {'Green': 140, 'Yellow': 230, 'Red': 231}
swap_classification["VEG"]["sugars"] = {'Green': 4,'Yellow': 7, 'Red': 8}

class Inventory:

    #initializes inventory with column labels
    def __init__(self):
        self.inv_df = pd.DataFrame(columns=['eanCode','upcCode','name','quantity','labels','allergies','ingredients',
                                            'nutrient_data','nutrient_levels','nutri_grade','categories','url',
                                            'swap_cat','swap_grade'])

    def get_inv(self):
        return self.inv_df

    #uses Open Food Facts Database api to access information about each barcode
    def search_product(self, code):
        search_url = 'https://world.openfoodfacts.org/api/v2/search?code='
        response = requests.get(search_url + code).json()['products']
        #data we're looking for
        key_list = ['product_name', 'categories', 'labels', 'ingredients', 'nutrition_grades_tags',
                    'nutrient_levels', 'nutriments', 'allergens', 'url']
        char_product = {}
        #returns an error if there is no barcode in open food facts
        if len(response) == 0:
            return {"ERROR": "Not in Open Food Facts"}
        item = response[0]
        #goes through each product data to find requested information, sets value to NA if it's not present
        for key in key_list:
            if key in item.keys():
                char_product[key] = item[key]
            else:
                char_product[key] = "NA"
        return char_product

    #convert ingredients data from Open Food Facts to a clean string
    def clean_ingredients(self, item_ingredients):
        ingredients = ""
        #returns an empty string if there's no ingredients provided
        if item_ingredients == 'NA' or item_ingredients == {} or len(item_ingredients) == 0:
            return ingredients
        #gets only the names of ingredients
        for i in range(len(item_ingredients)):
            if 'contains' not in item_ingredients[i]['text']:
                ingredients += item_ingredients[i]['text'] + ", "
        return ingredients

    #converts nutriment info from Open Food Facts to a usable dictionary
    def clean_nutriments(self, nutriments):
        nutrition_serving = {}

        if len(nutriments) > 0 and nutriments != "NA":
            #as long as there are nutrients left, splits up nutriments so that value and unit are seperated
            for key, val in nutriments.items():
                nutri = key.split("_")[0]
                if "-" in nutri:
                    nutri = nutri.replace("-", "_")
                if nutri not in nutrition_serving.keys():
                    nutrition_serving[nutri] = [-1, "na"]
                if '_serving' in key or '_value' in key:
                    nutrition_serving[nutri][0] = float(val)
                if '_unit' in key:
                    nutrition_serving[nutri][1] = val

        # convert measurements
        mg_units = ['sodium', 'cholesterol', 'calcium', 'potassium', 'iron']
        g_units = ['sugar', 'fat']
        for nutriment in nutrition_serving.keys():
            if nutriment in mg_units:
                # if it's in grams but should be in mg, convert
                if nutrition_serving[nutriment][1] == 'g':
                    nutrition_serving[nutriment][0] = nutrition_serving[nutriment][0] * 1000
                    nutrition_serving[nutriment][1] = 'mg'
            if nutriment in g_units:
                #if it's in mg but should be in grams, convert
                if nutrition_serving[nutriment][1] == 'mg':
                    nutrition_serving[nutriment][0] = nutrition_serving[nutriment][0] / 1000
                    nutrition_serving[nutriment][1] = 'g'

        return nutrition_serving

    #makes the nutrient levels data from Open Food Facts more usable
    def clean_nutri_levels(self, nlevels):
        nutrition_levels = {}
        if len(nlevels) > 0 and nlevels != "NA":
            for key, val in nlevels.items():
                nutri = key
                if "-" in key:
                    nutri = nutri.replace("-", "_")
                nutrition_levels[nutri] = val
        return nutrition_levels

    #given a code and quantity (optional), searches on open food facts,cleans data and then builds a product dictionary
    def create_product(self, code, num=1):
        e_code = code
        # searches for product in OpenFoodFacts Database
        char_product = self.search_product(e_code)
        #if the product wasn't found, creates a default dictionary with only code and quantity
        if "ERROR" in char_product.keys():
            product = {'eanCode':e_code,'upcCode':e_code[1:],'name':'NA','quantity':num,'labels':'NA',
                   'allergies':'NA','ingredients':'NA','nutrient_data':{},'nutrient_levels':{},'nutri_grade':'NA',
                   'categories':'NA','url':'NA'}
            return product

        # clean data and sets up the corresponding product dictionary
        nutrition_serving = self.clean_nutriments(char_product['nutriments'])
        nutrition_levels = self.clean_nutri_levels(char_product['nutrient_levels'])
        ingredients = self.clean_ingredients(char_product['ingredients'])
        if char_product['nutrition_grades_tags'][0].upper() in nutri_grades:
            grade = char_product['nutrition_grades_tags'][0].upper()
        else:
            grade = 'NA'
        product = {'eanCode':e_code,'upcCode':e_code[1:],'name':char_product['product_name'],'quantity':num,
                   'labels':char_product['labels'],'allergies':char_product['allergens'],'ingredients':ingredients,
                   'nutrient_data':nutrition_serving,'nutrient_levels':nutrition_levels,
                   'nutri_grade':grade,'categories':char_product['categories'],
                   'url':char_product['url']}
        return product

        # converts code to an eanCode when possible

    def convert_code(self, code):
        if code.isnumeric() == False:
            return code
        if len(code) == 6:
            code = code + "0"
        if len(code) == 7:
            code = "0" + code
        if len(code) == 8:
            # convert 8 digit to ean 13
            temp = code[:8]
            exp_dig = int(code[6])
            if exp_dig <= 2:
                code = temp[:3] + str(exp_dig) + "0000" + temp[3:6]
            elif exp_dig == 3:
                code = temp[:4] + "00000" + temp[4:6]
            elif exp_dig == 4:
                code = temp[:5] + "00000" + temp[5:6]
            else:
                code = temp + "00000" + str(exp_dig)
            code = code + gs1.calculate(code)
        if len(code) == 11:
            code = "0" + code
        if len(code) == 12:
            code = "0" + code
        if len(code) == 14 and code[0] == 0:
            code = code[1:]
        return code

    #returns true if ean code was found, false otherwise
    def find_item(self, code):
        return self.inv_df['eanCode'].isin([code]).any()

    #gets specific items from the dataframe
    def get_items(self,val,attribute='eanCode'):
        inv = self.inv_df
        items = []

        #if the attribute is a code or a swap category, only finds items that match it
        if attribute in ['eanCode','upcCode','swap_cat']:
            for row in inv[inv[attribute]==val].index:
                items.append(inv[inv[attribute]==val].loc[row].to_dict())

        #if the attribute is a score, finds all items that are meet or exceed it
        if attribute in ['swap_grade','nutri_grade']:
            if attribute == 'swap_grade':
                valid_list = list(swap_grades.keys())
            else:
                valid_list = nutri_grades
            if val in valid_list:
                searched_grades = valid_list[valid_list.index(val):]
                for row in inv[inv[attribute].isin(searched_grades)].index:
                    items.append(inv[inv[attribute].isin(searched_grades)].loc[row].to_dict())
            else:
                print('Not a valid grade')
        #otherwise, finds items which contains the key value
        if attribute in ['name','ingredients','labels','allergies','categories']:
            print(attribute,val)
            print(inv[inv[attribute].str.contains(val,case=False)])
            for row in inv[inv[attribute].str.contains(val,case=False)].index:
                items.append(inv[inv[attribute].str.contains(val,case=False)].loc[row].to_dict())

        #returns a list of product dictionaries
        return items


    #creates product or updates quantity based on user input
    def userInput(self, code, input, num=1):
        code = self.convert_code(code)
        present = self.find_item(code)
        inv = self.inv_df

        #if the product isn't already in dataframe, recreate df with the product dictionary as a new row (num=quantity)
        if present==False:
            product = self.create_product(code,num)
            if input == 'remove':
                product['quantity'] = 0
            new_inv = inv.to_dict('records')
            new_inv.append(product)
            self.inv_df = inv.from_records(new_inv)
            #categorize product by SWAP and then calculates its color
            self.categorize(code)
            self.calcSwap(code)
        #if it is present adds, removes, or sets quantity depending on the action requested
        else:
            #if user wants to add items
            if input == 'add':
                inv.loc[inv['eanCode'] == code,'quantity'] += num
            #if user wants to remove items, if more is removed than current quantity tells user and sets quantity to 0
            if input == 'remove':
                if inv.loc[inv['eanCode'] == code,'quantity'].values < num:
                    print('Removing more than we currently have!')
                    inv.loc[inv['eanCode'] == code, 'quantity'] = 0
                else:
                    inv.loc[inv['eanCode'] == code,'quantity'] -= num
            #if user wants to set quantity
            if input == 'set':
                inv.loc[inv['eanCode'] == code,'quantity'] = num

    #adds items from an imported CSV to the dataframe
    def importCSV(self, path,action):
        columns = [['eanCode','upcCode','ean barcode','barcode'],['quantity','num']]

        with open(path,'r',newline='') as csvfile:
            #gets delimiter and reads file
            dialect = csv.Sniffer().sniff(csvfile.readline(), ',;')
            csvfile.seek(0)
            reader = csv.DictReader(csvfile, delimiter=dialect.delimiter)
            labels = reader.fieldnames

            # finds the correct column index for code and quantity (allows users to have different column names)
            inds = {}
            # goes through possible labels for code and then possible labels for quantity
            for col in columns:
                for name in col:
                    for label in labels:
                        # if the label of column matches one of the valid names gets the column index
                        if label == name:
                            if columns.index(col) == 0:
                                inds['code'] = label
                            else:
                                inds['quantity'] = label
            # tells user that we are missing a column
            if len(inds) < 2:
                print('Error: Columns not Found')
                return
            for row in reader:
                code = str(row[inds['code']])

                quantity = int(row[inds['quantity']])
                #
                self.userInput(code, action, quantity)

    # categorizes item based on svc model
    def categorize(self,code):
        inv = self.inv_df
        item = self.get_items(code)[0]
        category = 'U'
        #if the name is unknown sets category to unknown
        if item['name'] == "NA" or item['name'] == None:
            inv.loc[inv['eanCode']==code,'swap_cat'] = category
            return category

        #access sav model
        modulePath = os.path.dirname(__file__)
        filePath = os.path.join(modulePath, 'item_category_svc_model.sav')
        #gets information needed for classification
        item_ingredients = str(item['ingredients'])
        text_features = item['name']
        if item['categories'] != None and item['categories']!= 'NA':
            text_features += ", " + item['categories']
        if item_ingredients != None and item_ingredients != 'NA':
            text_features += ", " + item_ingredients
        #cleans text
        text_features = text_features.lower()
        text_features = re.compile('[%s]' % re.escape(string.punctuation)).sub(' ', text_features)
        text_features = text_features.strip()
        #opens model and gets the predicted category
        with open(filePath, 'rb') as f:
            categorize_model = pickle.load(f)
        predict = categorize_model.predict([text_features])
        category = predict[0]

        #sets the product category to category
        inv.loc[inv['eanCode'] == code, 'swap_cat'] = category
        return category

    #determines SWAP classification (Red, Yellow, Green) for a given product code
    def calcSwap(self,code):
        inv = self.inv_df
        item = self.get_items(code)[0]
        nutrients = item['nutrient_data']
        category = item['swap_cat']

        # sets swap to unranked if we don't have all the nutrients
        if ('saturated_fat' not in nutrients) or ('sodium' not in nutrients) or ('sugars' not in nutrients) or (
                category == "U"):
            inv.loc[inv['eanCode'] == code, 'swap_grade'] = "U"
            return inv.loc[inv['eanCode'] == code, 'swap_grade']

        # gets nutrient info on sat fat (g), sodium (mg), and sugar (g)
        sat_fat = nutrients['saturated_fat'][0]
     
        sodium = nutrients['sodium'][0]
        sugar = nutrients['sugars'][0]
        classification = swap_classification[category]

        # uses this info to determine swap category (color matches the worst nutrient)
        swap = "U"
        #saturated fat
        if sat_fat <= classification['saturated_fat']['Green']:
            swap = "G"
        elif sat_fat <= classification['saturated_fat']['Yellow']:
            swap = "Y"
        elif sat_fat >= classification['saturated_fat']['Red']:
            swap = "R"
        #salt/sodium
        if sodium <= classification['sodium']['Green'] and swap not in ['R', 'Y']:
            swap = "G"
        elif sodium <= classification['sodium']['Yellow'] and swap not in ['R']:
            swap = "Y"
        elif sodium >= classification['sodium']['Red']:
            swap = "R"
        #sugar
        if sugar <= classification['sugars']['Green'] and swap not in ['R', 'Y']:
            swap = "G"
        elif sugar <= classification['sugars']['Yellow'] and swap not in ['R']:
            swap = "Y"
        elif sugar >= classification['sugars']['Red']:
            inv.loc[inv['eanCode'] == code, 'swap_grade'] = "R"

        #sets swap_grade to the derived swap
        inv.loc[inv['eanCode'] == code, 'swap_grade'] = swap
        return inv.loc[inv['eanCode'] == code, 'swap_grade']

class userInteraction:
    def __init__(self,inv):
        self.html_path = os.path.abspath('temp.html')
        self.inventory = inv

    #program homepage
    def home(self):
        print("Welcome to the simplified RE inventory app (uses a pandas dataframe rather than a database)!")
        print()

        #asks user what they would like to do
        response = ''
        
        #run functions based on their response
        while response != 'q':
            while response not in ['1', '2', '3', '4','5','6','7','q']:
                response = input('What would you like to do?\nView Inventory Table (1) \nSearch For Item (2) '
                                 '\nUpdate Quantity (3) \nConfirm Categories (4) \nVisualization Dashboard (5) '
                                 '\nMass Update Inventory Via CSV (6) \nExport Table as CSV (7)  \nQuit (q)')
                print()
            if response == '1':
                response = self.view_table(test_inv.inv_df.to_html())
            if response == '2':
                response = self.search_item()
            if response == '3':
                response = self.update_quantity()
            if response == '4':
                response = self.confirm_categories()
            if response == '5':
                response = self.viz_dashboard()
            if response == '6':
                response = self.read_csv()
            if response == '7':
                filename = input('Enter name of file to be created (enter to go back)')
                if filename != '':
                    self.inventory.inv_df.to_csv(filename, index=False)
                response = ''

    # opens up a browser tab that displays the inventory table
    def view_table(self, html):
        #gets html table and adds a head
        url = 'file://' + self.html_path
        head = "<h2>Inventory Table<h2>"

        #writes a html file and opens it
        with open(self.html_path, 'w') as f:
            f.write(head + html)
        webbrowser.open(url)

        #returns user to home page or ends program
        back = input('Press anything to go home (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

    #outputs the data of an item/row in dataframe
    def display_item(self,row):
        print('Barcode: ' + row['eanCode'])
        print('Name: ' + row['name'])
        print('Quantity: ' + str(row['quantity']))
        print('Raw Categories: ' + row['categories'])
        print('Labels: ' + row['labels'])
        print('Allergies: ' + row['allergies'])
        print('Ingredients: ' + row['ingredients'])
        if row['nutrient_levels'] != 'NA':
            for nutrient,level in row['nutrient_levels'].items():
                print(nutrient + ' Level: ' + level)
        print('Nutrigrade: ' + row['nutri_grade'])
        print('SWAP Category: ' + row['swap_cat'])
        print('SWAP Grade: ' + swap_grades[row['swap_grade']])
        print()

    #lets the user either update the quantity of an item found either by code or name or create the item if not found
    def update_quantity(self):
        print('Update quantity of an item')
        att = ''
        while att not in ['1','2']:
            att = input('How would you like to find the item? \nBy code (1) or name (2)?')

        #if searching by code
        if att == '1':
            key = input('Enter barcode')
            #repeatedly asks for input if the barcode length is incorrect
            while len(key) < 6 or (len(key) > 8 and len(key) < 12) or len(key)>13:
                key = input('Incorrect barcode length (should be 6,8,12,or 13)')
            #converts inputted code to an eanCode if necessary
            key = self.inventory.convert_code(key)
            #displays item if found, tells the user otherwise
            if self.inventory.find_item(key):
                item = self.inventory.get_items(key)[0]
                self.display_item(item)
            else:
                print('Item code not found, Will add it to the inventory')

        #if searching by name
        else:
            key = input('Enter name')
            items = self.inventory.get_items(key,'name')

            #displays all found items and asks user which one they are looking to update
            print('Items found. Which of the following are you looking for?')
            for i in range(len(items)):
                print(str(i)+"." + items[i]['name'])
                print("Barcode: " + items[i]['eanCode'])
                print('Category: ' + items[i]['swap_cat'])
                print('Quantity: ' + str(items[i]['quantity']))
                print()
            indx = 'none'
            while indx not in [str(i) for i in range(1,len(items))]:
                indx = input('Enter the correct index to update the item (enter to go back)')
                #go back home if user enters none
                if indx == '':
                    return ''
                print(indx)

            
            #otherwise sets key to the correct eanCode
            key = items[int(indx)]['eanCode']

        #asks user how they want to update quantity (do they want to add, remove, or set it; by how much)
        action = ''
        while action not in ['1','2','3']:
            action = input('Add (1), Remove (2), or Set (3) Quantity')
        quantity = int(input('Enter quantity added/removed/set'))
        print()
        #updates item quantity
        action_dic = {'1':'add','2':'remove','3':'set'}
        self.inventory.userInput(key,action_dic[action],quantity)
        #output new quantity of item
        print('New Quantity: ' + str(self.inventory.get_items(key)[0]['quantity']))

        # return home or quit
        back = input('Press anything to go home (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

    # searches for items by code, name, labels, ingredients, allergies, categories, and nutrition scores
    def search_item(self):
        att = ''
        attribute_dict = {'1':'eanCode','2':'name','3':'labels','4':'ingredients','5':'allergies','6':'categories',
                          '7':'swap_cat','8':'swap_grade','9':'nutri_grade'}
        search_str = ''
        key = ''
        for i,att in attribute_dict.items():
            search_str += (att + ' (' + i + ') \n')

        print('Search for items in inventory')
        print()
        #asks the user which attribute they are using to filter, only accepts valid attributes
        while att not in attribute_dict.keys():
            att = input('How would you like to search items?\nBy...\n'+search_str)

        #if searching by barcode
        if attribute_dict[att] == 'eanCode':
            key = input('Enter barcode')
            #checks barcode length
            while len(key) < 6 or (len(key) > 8 and len(key) < 12) or len(key) > 13:
                key = input('Incorrect barcode length (should be 6,8,12,or 13); press enter to go back')
                if key == '':
                    return ''
            #converts barcode to EANcode if needed
            key = self.inventory.convert_code(key)
            #tells user if nothing was found
            if self.inventory.find_item(key)==False:
                print('Item code not found')
        #searches by swap category
        elif attribute_dict[att] == 'swap_cat':
            search_str = ' '.join(categories)
            while key not in categories:
                key = input('Enter Desired SWAP category: (' + search_str+')').upper()
        #searches by swap grade
        elif attribute_dict[att] == 'swap_grade':
            while key.upper() not in list(swap_grades.keys()):
                key = input('Enter Desired SWAP grade: Green (G), Yellow (Y), Red (R)').upper()
        #searches by nutriscore
        elif attribute_dict[att] == 'nutri_grade':
            search_str = ' '.join(nutri_grades)
            while key.upper() not in nutri_grades:
                key = input('Enter Desired Nutri-score/grade: (' + search_str + ')').upper()
        #searches by other attributes
        else:
            key = input('Enter ' + attribute_dict[att]).lower()

        #gets all items associated with the key and displays each item with indices
        found_items = self.inventory.get_items(key,attribute_dict[att])
        print('The following items were found')
        for i in range(len(found_items)):
            print(str(i+1)+ '.')
            self.display_item(found_items[i])

        #user can export the selected items as a csv
        export = ''
        while export not in ['y', 'n']:
            export = input('Do you want to export the results as a csv (y/n)?').lower()
        if export == 'y':
            filename = input('Enter name of file to be created')
            pd.DataFrame.from_records(found_items).to_csv(filename)

        #user can open up a tab for the results table
        show_table = ''
        while show_table not in ['y','n']:
            show_table = input('Do you want to open up the results in a browser (y/n)?').lower()
        if show_table == 'y':
            self.view_table(pd.DataFrame.from_records(found_items).to_html())

        # return home or quit
        back = input('Press anything to go home (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

    #confirms that the swap category for each item is correct
    def confirm_categories(self):
        table = self.inventory.inv_df
        swap_cat_labels = [''] + list(swap_classification.keys())

        print('Are the following correct categories?')
        print()
        for index,row in table.iterrows():
            #display item data
            self.display_item(row)

            #ask user if the displayed SWAP category is correct
            correct = 'none'
            while correct not in ['y','n','Y','N','']:
                correct = input('Is the SWAP correct (y/n or enter to go back) ?')

            #if it's not print all possible labels and ask user to choose the correct one
            if correct == '':
                return ''
            if correct.lower() == 'n':
                for i in range(1,len(swap_cat_labels)):
                    print(swap_cat_labels[i] + " ("+str(i) +")")
                new_cat = input('Enter the correct category number')

                #repeats question if it's not valid
                while new_cat not in [str(i) for i in range(1,len(swap_cat_labels))]:
                    new_cat = input('Not a valid input')

                #sets swap_category and then recalculates SWAP score
                table.loc[index,'swap_cat'] = swap_cat_labels[int(new_cat)]
                self.inventory.calcSwap(row['eanCode'])

        # return home or quit
        back = input('Press enter to go back (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

    #creates data traces for a pie chart
    def tracePie(self,by=''):
        groups = self.inventory.inv_df.groupby(by)
        sums = groups['quantity'].sum()
        traces = {}
        for label,quantity in sums.items():
            traces[label.upper()] = quantity
        return traces

    #create data traces for category/quantity sunbursts
    def traceSunBurst(self):
        traces = {}
        #set index to muliIndex (cateogry,barcode) and sort by this index
        df = self.inventory.inv_df.set_index(['swap_cat','eanCode'])
        df = df.sort_index(level=[0,1])
        #get quantities,labels, and parents for each sector
        q_column = df['quantity']
        total = q_column.sum()
        parents = df.index.get_level_values(0)
        labels = df.index.get_level_values(1)
        quantities = list(q_column.values)
        counts = [q_column[cat].count() for cat in parents.unique()]

        #add a
        traces['parents'] = [''] + ['Total' for cat in parents.unique()] + list(parents)
        traces['labels'] = ['Total'] + [cat for cat in parents.unique()] + list(labels)
        traces['values'] = [total] + [q_column[cat].sum() for cat in parents.unique()] + quantities
        traces['info'] = [''] + [str(count) + " products" for count in counts] + ["Name: " + val[0] + "<br> SWAP Grade:" + swap_grades[val[1]] for val in df[['name','swap_grade']].values]

        return traces

    #create a scatter plot where users can compare products by different nutriments (marker size= quantity)
    def nutritionScatterPlot(self,by):
        #all possible nutriment keys and associated units
        nutrient_data_keys = ['calcium', 'carbohydrates', 'cholesterol', 'energy_kcal', 'fat', 'fiber', 'iron',
                              'potassium', 'proteins', 'sodium', 'saturated_fat', 'sugars']
        nutrient_units = ['mg', 'g', 'mg', 'kcal', 'g', 'g', 'mg', 'mg', 'g', 'mg', 'g', 'g']
        #sort inventory and then get a list of dictionaries (one for each product)
        inv = self.inventory.inv_df.sort_values(by=by)
        data = inv.to_dict(orient='records')
        traces = {}
        scatter_graph = go.Figure(layout={'title': {'text': 'Nutritional Data Bubble Plot', 'font_size': 24, 'xref': 'paper', 'x': 0.5}})

        #gets data needed for plot traces
        for item in data:
            #add a trace for a group if it's not already present
            if item[by] not in traces:
                traces[item[by]] = {'nutrient_data': {}, 'text': [],'size':[]}
            #set up hover text information
            levels = '<br></br> '.join([val[0] + "-----" + val[1] for val in item['nutrient_levels'].items()])
            traces[item[by]]['text'].append("<b>" + item['name'] + "</b>" + "<br></br>Barcode: " + item['eanCode'] +
                                            '<br></br>Quantity: ' + str(item['quantity']) + '<br></br>Nutrition:<br> '+ levels)
            #gets size for marker
            traces[item[by]]['size'].append(item['quantity'])
            #nutritional data for x/y
            for nutrient in nutrient_data_keys:
                #if the nutrient isnt already in the trace data adds the list
                if nutrient not in traces[item[by]]['nutrient_data']:
                    traces[item[by]]['nutrient_data'][nutrient] = []
                #if the nutrient is present in the item's data adds the value to the nutrient list, otherwise adds None
                if nutrient in item['nutrient_data']:
                    traces[item[by]]['nutrient_data'][nutrient].append(item['nutrient_data'][nutrient][0])
                else:
                    traces[item[by]]['nutrient_data'][nutrient].append(None)

        #gets all groups and adds traces for each group with x= sugar and y= calories
        groups = list(traces.keys())
        for group in groups:
            scatter_graph.add_trace(go.Scatter(name=group, mode='markers', x=traces[group]['nutrient_data']['sugars'],
                                        y=traces[group]['nutrient_data']['energy_kcal'],marker_size=traces[group]['size'],
                                        hovertext=traces[group]['text'],hoverinfo='text'))

        #builds buttons for both x and y axes so that user can choose which nutrient should be x and which should be y
        x_button = list([])
        y_button = list([])
        for nutrient in nutrient_data_keys:
            x_button.append(dict(
                method="update",
                args=[{'x': [traces[group]['nutrient_data'][nutrient] for group in groups]},
                      {'xaxis': {'title': nutrient + " (" + nutrient_units[nutrient_data_keys.index(nutrient)]+ ")"}}],
                label=nutrient,
            ))
            y_button.append(dict(
                method="update",
                args=[{'y': [traces[group]['nutrient_data'][nutrient] for group in groups]},
                      {'yaxis': {'title': nutrient + " (" + nutrient_units[nutrient_data_keys.index(nutrient)]+ ")"}}],
                label=nutrient,
            ))
        #update layout with xaxis/yaxis titles and created buttons
        scatter_graph.update_layout(xaxis={'title': "Sugars (g)"},yaxis={'title': "Energy (kcal)"},
                             updatemenus=[
                                 dict(buttons=x_button, direction="down",x=-0.05,y=1,xanchor='right',yanchor='top'),
                                 dict(buttons=y_button, direction="down",x=-0.05,y=0.85,xanchor='right',yanchor='top')
                                        ]
                                    )
        return scatter_graph

    # opens up a browser tab that displays some visualizations
    def viz_dashboard(self):
        #general layout for plots
        layout = {'title':{'font_size': 24, 'xref': 'paper', 'x': 0.5}}

        #trace sunburst, set up hover text and layout
        sunburst_trace = self.traceSunBurst()
        hover ='<b>%{label} </b> <br> Quantity: %{value}<br> %{hovertext}'
        # create sunburst chart for inventory quantity (total -> swap_cat -> barcode)
        inv_sunburst = go.Figure(go.Sunburst(labels=sunburst_trace['labels'], values=sunburst_trace['values'],
                                             parents=sunburst_trace['parents'], hovertext=sunburst_trace['info'],
                                             hovertemplate=hover,branchvalues="total"),layout=layout)
        inv_sunburst.update_layout({'title':{'text': 'Current Inventory Composition'}})

        #make pie chart subplot for nutrition scoring (SWAP and nutri-score)
        pie_fig = make_subplots(rows=1,cols=2,specs=[[{'type':'domain'}, {'type':'domain'}]])
        pie_fig.update_layout(layout)
        swap_trace = self.tracePie(by='swap_grade')
        nutri_trace = self.tracePie(by='nutri_grade')

        #get labels and colors for both pie charts
        swap_labels = [swap_grades[label] for label in list(swap_trace.keys())]
        swap_colors = [COLOR_MAPPING[swap] for swap in list(swap_trace.keys())]
        nutri_labels = [label.upper() for label in list(nutri_trace.keys())]
        nutri_colors = [COLOR_MAPPING[label] for label in nutri_labels]
        line = dict(color='#000000', width=2)
        hover = '<b>%{label}</b> <br>%{value} Items<br> %{percent} of inventory'
        #add traces
        pie_fig.add_trace(go.Pie(labels=swap_labels,values=list(swap_trace.values()),name='SWAP Grade',
                                 legendgrouptitle={'text':'SWAP grade'},legendgroup='swap',hovertemplate=hover,
                                 textfont={'size':16},marker={'colors':swap_colors,'line':line}),1,1)
        pie_fig.add_trace(go.Pie(labels=list(nutri_trace.keys()),values=list(nutri_trace.values()),name='Nutri-score',
                                 legendgrouptitle={'text':'Nutri-score'}, legendgroup='2',hovertemplate=hover,
                                 textfont={'size':16}, marker={'colors':nutri_colors,'line':line}),1,2)
        pie_fig.update_layout({'title':{'text': 'Healthiness of Inventory'}})

        #finally create a nutrition bubble plot
        scatter_fig = self.nutritionScatterPlot(by='swap_cat')

        #creates the html string for all figures
        html = inv_sunburst.to_html()
        html += pie_fig.to_html(full_html=False)
        html += scatter_fig.to_html(full_html=False)

        # writes a html file and opens it
        with open(self.html_path, 'w') as f:
            f.write(html)
        webbrowser.open('file://' + self.html_path)

        # return home or quit
        back = input('Press anything to go home (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

    def read_csv(self):
        action_dic = {'1': 'add', '2': 'remove', '3': 'set'}

        print('Mass Import Via CSV')
        print()
        filename = input('Enter filename of inventory you want imported (default is usda_inventory_small.csv)')
        if filename == '':
            filename = 'usda_inventory_small.csv'

        #checks if the file is in directory
        while os.path.isfile(filename) == False:
            filename = input('Filename not found in directory! Try again (no default)')
            if filename == '':
                return ''
        #checks if the file is a csv
        if filename.endswith('.csv') == False:
            print('Import Error: Must be a CSV')
        else:
            #asks user what action they would like to take and then imports CSV into dataframe
            action = ''
            while action not in ['1','2','3']:
                action = input('Would you like to add(1), remove(2), or set(3)?')
            print('updating...')
            self.inventory.importCSV(filename,action_dic[action])

        # return home or quit
        back = input('Press anything to go home (q to quit)')
        if back == 'q':
            return 'q'
        else:
            return ''

if __name__ == '__main__':
    test_inv = Inventory()
    UI = userInteraction(test_inv)
    UI.home()

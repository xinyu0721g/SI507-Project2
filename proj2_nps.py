import requests
import json
from bs4 import BeautifulSoup
import secrets
import plotly.plotly as py


API_KEY = secrets.google_places_key


state_info = open('states_info.json', 'r')
state_info_json = state_info.read()
state_info_python = json.loads(state_info_json)
state_info.close()


class NationalSite:
    def __init__(self, type, name, desc='', url=None):
        self.type = type
        self.name = name
        self.description = desc
        self.url = url

        if url is not None:
            detail_html = get_from_cache('site_detail_cache.json', url)
            detail_soup = BeautifulSoup(detail_html, 'html.parser')
            self.address_street = detail_soup.find('span', itemprop="streetAddress").text.strip().replace('\n', '')
            self.address_city = detail_soup.find('span', itemprop="addressLocality").text.strip()
            self.address_state = detail_soup.find('span', itemprop="addressRegion").text.strip()
            self.address_zip = detail_soup.find('span', itemprop="postalCode").text.strip()
            self.address = '{}, {}, {}'.format(self.address_street, self.address_city, self.address_state)

    def __str__(self):
        address_string = '{}, {}, {} {}'.format(self.address_street, self.address_city, self.address_state, self.address_zip)
        return '{} ({}): {}'.format(self.name, self.type, address_string)


class NearbyPlace:
    def __init__(self, name, location_dict=None):
        self.name = name
        if location_dict is not None:
            self.lat = location_dict['lat']
            self.lon = location_dict['lng']
        else:
            self.lat = ''
            self.lon = ''

    def __str__(self):
        return self.name


def params_unique_combination(baseurl, params):
    if params is not None:
        alphabetized_keys = sorted(params.keys())
        res = []
        for k in alphabetized_keys:
            res.append("{}-{}".format(k, params[k]))
        identifier = baseurl + "_".join(res)
    else:
        identifier = baseurl
    return identifier


def get_from_cache(cache_fname, baseurl, params=None):
    unique_identifier = params_unique_combination(baseurl, params)
    try:
        infile = open(cache_fname, 'r')
        infile_content = infile.read()
        diction = json.loads(infile_content)
        infile.close()
    except:
        diction = {}
    if unique_identifier in diction:
        # print('Getting data from cache...')
        content = diction[unique_identifier]
    else:
        # print('Getting data from new request...')
        content = requests.get(baseurl, params).text
        diction[unique_identifier] = content
        dumped_dict = json.dumps(diction, indent=2)
        outfile = open(cache_fname, 'w')
        outfile.write(dumped_dict)
        outfile.close()
    return content


def get_sites_for_state(state_abbr):
    regional_url = 'https://www.nps.gov/state/{}/index.htm'.format(state_abbr)
    cache_fname = 'state_sites_cache.json'
    html = get_from_cache(cache_fname, regional_url)
    soup = BeautifulSoup(html, 'html.parser')
    site_divs = soup.find(id="list_parks").find_all(class_="clearfix")
    site_lst = []
    for site in site_divs:
        site_type = site.find('h2').text
        site_name = site.find('h3').text
        site_desc = site.find('p').text
        url_tail = site.h3.a['href']
        detail_url = 'https://www.nps.gov{}index.htm'.format(url_tail)
        site = NationalSite(site_type, site_name, site_desc, detail_url)
        site_lst.append(site)
    return site_lst


def get_pyob_from_google_places(name, type):
    baseurl = 'https://maps.googleapis.com/maps/api/place/textsearch/json'
    params = {'query': name, 'type': type, 'key': API_KEY}
    result = get_from_cache('GPS_coordinates_cache.json', baseurl, params)
    python_object = json.loads(result)
    return python_object


def get_loca_dict_and_address(name, type):
    python_object = get_pyob_from_google_places(name, type)
    if python_object['status'] == 'OK':
        location_dict = python_object['results'][0]['geometry']['location']
    else:
        location_dict = None
    return location_dict


def get_GPS_coordinates(national_site):
    name = national_site.name
    type = national_site.type
    location_dict = get_loca_dict_and_address(name, type)
    if location_dict is None:
        name = ''.join(national_site.name.split())
        location_dict = get_loca_dict_and_address(name, type)
    if location_dict is not None:
        (lat, lon) = (location_dict['lat'], location_dict['lng'])
        return lat, lon
    else:
        return None


def get_nearby_places_for_site(national_site):
    nearbyplaces_lst = []
    if get_GPS_coordinates(national_site) is not None:
        (lat, lon) = get_GPS_coordinates(national_site)
        location = '{}, {}'.format(lat, lon)
        baseurl = 'https://maps.googleapis.com/maps/api/place/nearbysearch/json'
        params = {'location': location, 'radius': 10000, 'key': API_KEY}
        result = get_from_cache('nearby_places_cache.json', baseurl, params)
        python_object = json.loads(result)
        for i in python_object['results']:
            national_site_name = national_site.name + ' ' + national_site.type
            if i['name'] != national_site_name:
                nearby_place = NearbyPlace(i['name'], i['geometry']['location'])
                nearbyplaces_lst.append(nearby_place)
    return nearbyplaces_lst


def check_in_state(lat, lon, state_abbr):
    state_dict = state_info_python[state_abbr.upper()]
    min_lat = state_dict['min_lat']
    max_lat = state_dict['max_lat']
    min_lon = state_dict['min_lng']
    max_lon = state_dict['max_lng']
    if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
        return True
    else:
        return False


def get_useful_national_sites(state_abbr):
    national_sites = []
    for i in get_sites_for_state(state_abbr):
        if get_GPS_coordinates(i) is not None:
            lat, lon = get_GPS_coordinates(i)
            if check_in_state(lat, lon, state_abbr) is True:
                national_sites.append(i)
    return national_sites


def get_coordinates_range(lat_vals, lon_vals):
    min_lat = 10000
    max_lat = -10000
    min_lon = 10000
    max_lon = -10000

    for str_v in lat_vals:
        v = float(str_v)
        if v < min_lat:
            min_lat = v
        if v > max_lat:
            max_lat = v
    for str_v in lon_vals:
        v = float(str_v)
        if v < min_lon:
            min_lon = v
        if v > max_lon:
            max_lon = v
    return min_lat, max_lat, min_lon, max_lon


def get_centers(lat_vals, lon_vals):
    min_lat, max_lat, min_lon, max_lon = get_coordinates_range(lat_vals, lon_vals)
    center_lat = (max_lat + min_lat) / 2
    center_lon = (max_lon + min_lon) / 2
    return center_lat, center_lon


def get_axis(lat_vals, lon_vals):
    min_lat, max_lat, min_lon, max_lon = get_coordinates_range(lat_vals, lon_vals)
    max_range = max(abs(max_lat - min_lat), abs(max_lon - min_lon))
    padding = max_range * .10
    lat_axis = [min_lat - padding, max_lat + padding]
    lon_axis = [min_lon - padding, max_lon + padding]
    return lat_axis, lon_axis


def plot_sites_for_state(state_abbr):
    national_sites = get_useful_national_sites(state_abbr)
    lat_vals = []
    lon_vals = []
    text_vals = []
    for i in national_sites:
        lat, lon = get_GPS_coordinates(i)
        lat_vals.append(lat)
        lon_vals.append(lon)
        text_vals.append(i.name)

    data = [dict(
        type='scattergeo',
        locationmode='USA-states',
        lon=lon_vals,
        lat=lat_vals,
        text=text_vals,
        mode='markers',
        marker=dict(
            size=8,
            symbol='star',
        ))]

    center_lat, center_lon = get_centers(lat_vals, lon_vals)
    lat_axis, lon_axis = get_axis(lat_vals, lon_vals)

    layout = dict(
        title='National Sites in {}'.format(state_info_python[state_abbr.upper()]['name']),
        geo=dict(
            scope='usa',
            projection=dict(type='albers usa'),
            showland=True,
            landcolor="rgb(250, 250, 250)",
            subunitcolor="rgb(100, 217, 217)",
            countrycolor="rgb(217, 100, 217)",
            lataxis={'range': lat_axis},
            lonaxis={'range': lon_axis},
            center={'lat': center_lat, 'lon': center_lon},
            countrywidth=3,
            subunitwidth=3
        ))
    fig = dict(data=data, layout=layout)
    py.plot(fig, validate=False, filename='National Sites in {}'.format(state_info_python[state_abbr.upper()]['name']))


def plot_nearby_for_site(site_object):
    if get_GPS_coordinates(site_object) is None:
        print('Google Places can’t find GPS coordinates for this site...')
    else:
        site_lat, site_lon = get_GPS_coordinates(site_object)
        site_name = site_object.name
        nearbys = get_nearby_places_for_site(site_object)
        nearby_lat_vals = []
        nearby_lon_vals = []
        nearby_text_vals = []
        for nearby_site in nearbys:
            nearby_lat_vals.append(nearby_site.lat)
            nearby_lon_vals.append(nearby_site.lon)
            nearby_text_vals.append(nearby_site.name)
        all_lat_vals = nearby_lat_vals + [site_lat]
        all_lon_vals = nearby_lon_vals + [site_lon]

        trace1 = dict(
            type='scattergeo',
            locationmode='USA-states',
            lon=[site_lon],
            lat=[site_lat],
            text=[site_name],
            mode='markers',
            name=site_name,
            marker=dict(
                size=20,
                symbol='star',
                color='red'
            ))
        trace2 = dict(
            type='scattergeo',
            locationmode='USA-states',
            lon=nearby_lon_vals,
            lat=nearby_lat_vals,
            text=nearby_text_vals,
            mode='markers',
            name='nearby places',
            marker=dict(
                size=8,

                symbol='circle',
                color='blue'
            ))

        data = [trace1, trace2]

        lat_axis, lon_axis = get_axis(all_lat_vals, all_lon_vals)
        center_lat, center_lon = get_centers(all_lat_vals, all_lon_vals)

        layout = dict(
            title='Places near {} {}'.format(site_object.type, site_object.name),
            geo=dict(
                scope='usa',
                projection=dict(type='albers usa'),
                showland=True,
                landcolor="rgb(250, 250, 250)",
                subunitcolor="rgb(100, 217, 217)",
                countrycolor="rgb(217, 100, 217)",
                lataxis={'range': lat_axis},
                lonaxis={'range': lon_axis},
                center={'lat': center_lat, 'lon': center_lon},
                countrywidth=3,
                subunitwidth=3
            ))
        fig = dict(data=data, layout=layout)
        py.plot(fig, validate=False, filename='Places near {} {}'.format(site_object.type, site_object.name))


if __name__ == '__main__':
    option = ''
    base_prompt = 'Enter command (or "help"for options):'
    feedback = ''
    current_state = ''
    while True:
        action = input(feedback + "\n" + base_prompt)
        feedback = ""
        words = action.split()

        if len(words) > 0:
            command = words[0]
        else:
            command = None

        if command == 'help':
            feedback += '''       
    list <stateabbr>
       available anytime
       lists all National Sites in a state
       valid inputs: a two-letter state abbreviation
    nearby <result_number>
       available only if there is an active result set
       lists all Places nearby a given result
       valid inputs: an integer 1-len(result_set_size)
    map
       available only if there is an active result set
       displays the current results on a map
    exit
       exits the program
    help
       lists available commands (these instructions)
    '''
        elif command == 'list':
            if len(words) > 1:
                stateabbr = words[1]
                if stateabbr.upper() in state_info_python:
                    current_state = 'list'
                    site_lst = get_sites_for_state(stateabbr)
                    feedback += 'National Sites in {}\n'.format(state_info_python[stateabbr.upper()]['name'])
                    for i in range(len(site_lst)):
                        feedback += '{} {}\n'.format(i+1, site_lst[i].__str__())
                else:
                    feedback += "I didn't recognize that state abbreviation. Please try again.\n"
            else:
                feedback += "I didn't recognize that state abbreviation. Please try again.\n"
        elif command == 'nearby':
            if current_state == 'list':
                if len(words) > 1:
                    try:
                        num = int(words[1])
                    except:
                        feedback += "This number is not valid. Please try again.\n"
                        continue
                    if 1 <= num <= len(site_lst):
                        current_state = 'nearby'
                        national_site = site_lst[num-1]
                        feedback += 'Places near {} {}\n'.format(national_site.name, national_site.type)
                        nearbys = get_nearby_places_for_site(national_site)
                        for i in range(len(nearbys)):
                            feedback += '{} {}\n'.format(i+1, nearbys[i].name)
                    else:
                        feedback += "This number is not valid. Please try again.\n"
                else:
                    feedback += "I didn't recognize that number. Please try again.\n"
            else:
                feedback += "This command is not valid now because there is no active result set.\n"
        elif command == 'map':
            if current_state == 'list':
                plot_sites_for_state(stateabbr)
            elif current_state == 'nearby':
                plot_nearby_for_site(national_site)
            else:
                feedback += "This command is not valid now because there is no active result set.\n"
        elif command == 'exit':
            print('Bye!')
            break
        else:
            feedback += "I didn't understand that. Please try again."

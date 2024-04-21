#!pip install dash
#!pip install jupyter-dash
#!pip install wget

import pandas as pd
import zipfile
import wget
import json
from urllib.request import urlopen

import plotly as plt
import plotly.graph_objs as go
import plotly.express as px
from plotly.subplots import make_subplots

import datetime
from dateutil.parser import parse

from dash import Dash, html, dcc, Input, Output


url = 'https://github.com/Palladain/Deep_Python/raw/main/Homeworks/Homework_1/archive.zip'
filename = wget.download(url)

with zipfile.ZipFile(filename, 'r') as zip_ref:
    zip_ref.extractall('./')

customers = pd.read_csv('olist_customers_dataset.csv')
location = pd.read_csv('olist_geolocation_dataset.csv')
items = pd.read_csv('olist_order_items_dataset.csv')
payments = pd.read_csv('olist_order_payments_dataset.csv')
reviews = pd.read_csv('olist_order_reviews_dataset.csv')
orders = pd.read_csv('olist_orders_dataset.csv')
products = pd.read_csv('olist_products_dataset.csv')
translation = pd.read_csv('product_category_name_translation.csv')
sellers = pd.read_csv('olist_sellers_dataset.csv')


# Brazil coordinates / shape
with urlopen(
    "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/brazil-states.geojson"
) as response:
    brazil = json.load(response)

# Since the database doesn't have an ID or feature using which values will be mapped between the coordinate/shape database and soybean database, we are adding an ID ourselves.
for feature in brazil["features"]:
    feature["id"] = feature["properties"]["sigla"]

# Здесь в качестве id, который будет отображаться, указано сокращение названия штата (как и в наших данных)

app = Dash(__name__)

colors = {
    'background': '#111111',
    'text': '#7FDBFF'
}

def strip_date_day(x):
    x = x.replace(minute=0)
    x = x.replace(second=0)
    x = x.replace(hour=0)
    return x

def strip_date_month(x):
    x = x.replace(minute=0)
    x = x.replace(second=0)
    x = x.replace(hour=0)
    x = x.replace(day=1)
    return x

# для получения строки из времени
copy_orders = orders.copy()[['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp']]
copy_orders.dropna(inplace=True)
copy_orders["time_parsed"] = copy_orders.order_purchase_timestamp.apply(lambda x: parse(x))
copy_orders["dates"] = copy_orders.time_parsed.apply(lambda x: strip_date_day(x))
date_zero = parse("2000-01-01")
copy_orders["days"] = copy_orders.dates.apply(lambda x: (x - date_zero).days)

months = pd.DataFrame()
months["month_dates"] = pd.date_range(start = copy_orders.dates.min(), end = copy_orders.dates.max(), freq = '2M')
months["month_days"] = months.month_dates.apply(lambda x: (x - date_zero).days)
month_dates_days_pairs = list(zip(months.month_dates, months.month_days))

'''товары по категориям'''
extra_translation = pd.DataFrame([["portateis_cozinha_e_preparadores_de_alimentos", "portable kitchen and food preparers"],
                                      ["pc_gamer", "PC Gamer"]], columns=["product_category_name", "product_category_name_english"])

product_id_category = products[['product_category_name', 'product_id']]
product_id_category = pd.merge(pd.concat([translation, extra_translation]), product_id_category, on="product_category_name")
product_id_category.drop(["product_category_name"], axis=1, inplace=True)

# распределение по категориям продаж (то есть по тому, что продают селлеры) в штате
seller_categories = pd.merge(product_id_category, items[["product_id", "seller_id", "order_id"]], on="product_id").drop(["product_id"], axis=1)
seller_categories = pd.merge(seller_categories, sellers[["seller_id", "seller_state"]], on="seller_id")#.drop(["seller_id"], axis=1)
seller_categories = pd.merge(seller_categories, copy_orders[["order_id", "order_status", "days"]], on="order_id").drop(['order_id'], axis=1)
seller_categories["cnt"] = 1

# распределение по категориям покупок (то есть по тому, что покупают пользователи) в штате
customer_categories = pd.merge(product_id_category, items[["product_id", "order_id"]], on="product_id").drop(["product_id"], axis=1)
customer_categories = pd.merge(customer_categories, copy_orders[["order_id", "customer_id", "order_status", "days"]], on="order_id").drop(["order_id"], axis=1)
customer_categories = pd.merge(customer_categories, customers[["customer_state", "customer_id"]], on="customer_id")#.drop(["customer_id"], axis=1)
customer_categories["cnt"] = 1


app.layout = html.Div(children=[
    html.Div([
      html.Div([
        dcc.Dropdown(
            ['Brazil'] + customers.customer_state.unique().tolist(),
            'Brazil',
            id='state-input'
        )
      ], style={'width': '49%', 'display': 'inline-block'}
      ),
      html.Div([
        dcc.Dropdown(
            orders.order_status.unique(),
            orders.order_status.unique(),
            multi=True,
            id='status-input'
        )
      ], style={'width': '49%', 'display': 'inline-block'}
      )
    ], style={'padding': '10px 5px'}),
    html.Div([
    html.Div([
        dcc.Graph(
        id='seller-distribution'
    )], style={'width': '49%', 'display': 'inline-block', 'padding': '0 20'}),

    html.Div([
        dcc.Graph(
        id='customer-distribution'
    )], style={'display': 'inline-block', 'width': '49%'}),
    ]),
    html.Div(
        dcc.RangeSlider(
            copy_orders.days.min(),
            copy_orders.days.max(),
            step=1,
            id='day-slider',
            value=[copy_orders.days.min(), copy_orders.days.max()],
            marks = {day : f"{date : %B %Y}" for date, day in month_dates_days_pairs}
        )
    , style={ 'padding': '0px 20px 20px 20px'}),
    html.Div([
    html.Div([
        dcc.RadioItems(
        ['Sellers', 'Customers'],
        'Customers',
        id='radio-for-map',
        inline=True
        )], style={'display':'flex', 'justifyContent' :'center'}),
    html.Div([
        dcc.Graph(
        id='map'
        )])
    ])
])

@app.callback(
    Output('state-input', 'value'),
    Input('map', 'clickData'),
    prevent_initial_call=True
)
def click_state_change(clickData):
    state = clickData['points'][0]['location']
    return state

@app.callback(
    Output('seller-distribution', 'figure'),
    Input('state-input', 'value'),
    Input('status-input', 'value'),
    Input('day-slider', 'value'))
def update_left_graph(state_value, status_values, day_values):
    res = seller_categories.copy()[seller_categories.order_status.isin(status_values)]

    res = res[res.days >= day_values[0]]
    res = res[res.days <= day_values[1]]

    if state_value != 'Brazil':
      res = res[res.seller_state == state_value]
    res = res.groupby(["product_category_name_english"]).count().reset_index()
    res.drop(["seller_state"], axis=1, inplace=True)

    fig = px.bar(res, y='product_category_name_english', x='cnt')
    fig.update_layout(title = {"text": f"Распределение по категориям продаж в {state_value}","x": 0.5})
    return fig


@app.callback(
    Output('customer-distribution', 'figure'),
    Input('state-input', 'value'),
    Input('status-input', 'value'),
    Input('day-slider', 'value'))
def update_right_graph(state_value, status_values, day_values):
    res = customer_categories.copy()[customer_categories.order_status.isin(status_values)]

    res = res[res.days >= day_values[0]]
    res = res[res.days <= day_values[1]]

    if state_value != 'Brazil':
      res = res[res.customer_state == state_value]
    res = res.groupby(["product_category_name_english"]).count().reset_index()
    res.drop(["customer_state"], axis=1, inplace=True)
    fig = px.bar(res, y='product_category_name_english', x='cnt')
    fig.update_layout(title = {"text": f"Распределение по категориям покупок в {state_value}","x": 0.5})
    return fig


@app.callback(
    Output('map', 'figure'),
    Input('status-input', 'value'),
    Input('day-slider', 'value'),
    Input('radio-for-map', 'value'),
    Input('state-input', 'value')
)
def update_map(status_values, day_values, radio_value, state_value):
    if radio_value == 'Sellers':
        filtered_sellers = seller_categories.copy()[seller_categories.order_status.isin(status_values)]
        filtered_sellers = filtered_sellers[filtered_sellers.days >= day_values[0]]
        filtered_sellers = filtered_sellers[filtered_sellers.days <= day_values[1]]

        if state_value != 'Brazil':
            filtered_sellers = filtered_sellers[filtered_sellers.seller_state == state_value]

        sellers_cnt = filtered_sellers.groupby(['seller_state']).agg({'seller_id' : 'nunique'}).reset_index()

        if state_value == 'Brazil':
            beb = pd.DataFrame({'seller_state' : customers.customer_state.unique()}) # чтобы отрисовывались все штаты, если выбрана вся Бразилия
        else:
            beb = pd.DataFrame({'seller_state' : [state_value]})
        sellers_cnt = pd.merge(sellers_cnt, beb, how='outer')
        sellers_cnt.fillna(value={'seller_id' : 0}, inplace=True)

        fig = px.choropleth(
            sellers_cnt, geojson=brazil, color='seller_id',
            locations='seller_state', featureidkey='id',
            range_color=[0, sellers_cnt.seller_id.max()],
            labels={'seller_state' : 'штат', 'seller_id': 'количество продавцов'})
    else:
        filtered_customers = customer_categories.copy()[customer_categories.order_status.isin(status_values)]
        filtered_customers = filtered_customers[filtered_customers.days >= day_values[0]]
        filtered_customers = filtered_customers[filtered_customers.days <= day_values[1]]

        if state_value != 'Brazil':
            filtered_customers = filtered_customers[filtered_customers.customer_state == state_value]

        # подсчет количества покупателей
        customers_cnt = filtered_customers.groupby(['customer_state']).agg({'customer_id' : 'nunique'}).reset_index()

        if state_value == 'Brazil':
            beb = pd.DataFrame({'customer_state' : customers.customer_state.unique()}) # чтобы отрисовывались все штаты
        else:
            beb = pd.DataFrame({'customer_state' : [state_value]})
        customers_cnt = pd.merge(customers_cnt, beb, how='outer')
        customers_cnt.fillna(value={'customer_id' : 0}, inplace=True)

        fig = px.choropleth(
            customers_cnt, geojson=brazil, color='customer_id',
            locations='customer_state', featureidkey='id',
            range_color=[0, customers_cnt.customer_id.max()],
            labels={'customer_state' : 'штат', 'customer_id': 'количество покупателей'})

    fig.update_geos(fitbounds="locations", visible=True)
    return fig


if __name__ == '__main__':
    app.run_server(debug=True)

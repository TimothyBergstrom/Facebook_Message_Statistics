#!/usr/bin/env python
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import json
import time
import datetime
import emoji as emoji_module
import re
import pdb
import seaborn
import matplotlib.pyplot as plt
import plotly
import plotly.plotly as pltly
import plotly.graph_objs as go
import warnings
import logging
logging.basicConfig(filename='logger.log',level=logging.DEBUG)

# Sizes are hardcoded (for now)
plot_width = 1000
plot_height = 500

def get_messages(filename):
    """Puts all messages in lists
    Written to be easy to follow, not to be compact"""

    logging.info(f'Opening {filename}')
    """Main script that finds all data"""
    # Open file in utf-8, or this will not work
    with open(filename, 'r', encoding='utf-8') as file:
        contents = file.read()

    logging.info(f'Parsing html with bs4')
    # "Soupify" contents, so it can be used in parsing
    parsed_html = BeautifulSoup(contents, 'lxml')

    logging.info('Parsing messages')
    # Find all div tags with class is some wierd stuff, all info can be found with this
    all_messages = parsed_html.body.find_all('div', attrs={'class': 'pam _3-95 _2pi0 _2lej uiBoxWhite noborder'})
    # was previously 'message' in class

    logging.info('Fixing corrupted unicode')
    # For bad unicode symbols
    with open('conversion/bad_unicode_fix.txt', 'r', encoding='utf-8-sig') as file:
        contents = file.read()
        char_dict = json.loads(contents)

    # For changing ascii smileys to unicode emojis
    with open('conversion/ascii_to_emoji.txt', 'r', encoding='utf-8-sig') as file:
        contents = file.read().replace("\\", "\\\\")  # Json cant load \\ :/
        ascii_to_emoji_dict = json.loads(contents)
        # only way to fix this :/
        for key in ascii_to_emoji_dict.keys():
            if "\\\\" in key:
                new_key = key.replace('\\\\', '\\')
                ascii_to_emoji_dict[new_key] = ascii_to_emoji_dict[key]
                del ascii_to_emoji_dict[key]

    all_texts = []
    all_users = []
    all_timestamps = []
    total_call_time = 0

    logging.info('Extracting messages')
    total_time = 0
    for number,message in enumerate(all_messages):
        # ETA time
        time_cycle = time.time()

        # Texts
        text = find_text(message)
        text, tags = text_cleaner(text, char_dict, ascii_to_emoji_dict)
        all_texts.append(text)
        # Users
        # Was once 'span'
        user = message.find('div', attrs={'class': '_3-96 _2pio _2lek _2lel'}).get_text()
        # Class was once 'user'
        all_users.append(user)

        # Call time (easiest to do it here)
        call_time = 0
        if message.find('span', attrs={'class': '_idm'}) is not None:
            captured_call_string = message.find('span', attrs={'class': '_idm'}).get_text()
            captured_call_string = captured_call_string.split(' ')
            # captured_call_string[0] = Längd or some other junk
            call_time = int(captured_call_string[1])
            if 'sec' in captured_call_string[2] or 'sek' in captured_call_string[2]:
                call_time = call_time / 60  # if second
            else:
                pass
        total_call_time += call_time

        # Timestamps
        timestamp = message.find('div', attrs={'class': '_3-94 _2lem'}).get_text()
        # Class was once 'meta'
        timestamp = timestamp_fixer(timestamp)
        all_timestamps.append(timestamp)

        # Progress
        progressed_time = time.time() - time_cycle
        total_time += progressed_time
        # number + 1 since it starts at 0
        mean_progressed_time = total_time/(number + 1)
        eta = round(mean_progressed_time*(len(all_messages) - number))
        s = f'{number + 1} out of {len(all_messages)} messages done - ETA {eta} seconds'
        print(' ' * 100, end='\r') # This is quite stupid, but it works when clearing previous line
        print(s, end='\r')
    print('')  # Clear \r
    return all_texts, all_users, all_timestamps, total_call_time

def find_text(message):
    """
    # Problem: Messages are not found in tags, plaintext between tags
    # Solution: Capture everything that is not a div tag between div tags
    message = soup object that lies between texts
    """
    text = message.find('div', attrs={'class': '_3-96 _2let'}).get_text()
    text = text.replace('<div>', '')
    text = text.replace('</div>', '')
    return text

    """
    # old, was before with <p>
    text = u''
    while True:
        p = message.find_next_sibling()
        if p == None:  # Prone to buggyness, fix for end of all texts
            break
        elif p.name == 'div':
            break
        elif p.name == 'p':
            text += str(p)
            message = p  # overwrite section, or it will loop forever
        else:
            text += str(p)
            message = p  # overwrite section, or it will loop forever
    return text
    """

def text_cleaner(text, char_dict={}, ascii_to_emoji_dict = {}):
    """
    # Problem: Messages sometimes messy with ascii emojis, links, pictures, stickers and such
    # Solution: Clean,replace and remove everything unwanted
    """
    text = text.replace('<p>', '')  # Remove <p>
    text = text.replace('</p>', '') # Remove </p>

    # Check for images, videos, stickers etc
    warnings.filterwarnings("ignore", category=UserWarning, module='bs4')  # Supress URL errors
    if bool(BeautifulSoup(text, "html.parser").find()):
        tags = BeautifulSoup(text, "html.parser").find_all()
        for tag in tags:
            text = text.replace(str(tag), '')  # Needs to make tag into string
    else:
        tags = ['']
    warnings.filterwarnings("always", category=UserWarning, module='bs4')  # Restart warnings

    # Fixed bugged symbols, japan/samsung
    for char in text:
        if char in char_dict.keys():
            text = text.replace(char, char_dict[char])

    # Fix ascii smileys to unicode
    for ascii_emoji in ascii_to_emoji_dict.keys():
        if ascii_emoji in text:
            text = text.replace(ascii_emoji, ascii_to_emoji_dict[ascii_emoji])

    return text, tags

def timestamp_fixer(timestamp):
    """
    # Problem: Messages are in a bad format, cannot be used to make datetime objects
    # Solution: Replace and reformat all dates, converting
    den 15 februari 2018 kl. 12:40 UTC+01
    to
    2018-02-15 12:40:00 Thursday
    Month dict is in swedish, change conversion file if another language is used"""
    with open('conversion/month_converter.txt', 'r', encoding='utf-8') as file:
        month_converter = json.loads(file.read())
    timestamp = timestamp.split(' ')
    # timestamp[0] = den
    day = timestamp[1]
    month = month_converter[timestamp[2]]
    year = timestamp[3]
    # timestamp[4] = kl.  # <-- old had kl. first
    hour_minute = timestamp[4]  # Assume seconds are 00
    # timestamp[6] = timezone, might be useful?
    timestamp = f'{year}-{month}-{day} {hour_minute}:00'
    datetime_obj = datetime.date(int(year), int(month), int(day))
    weekday_dict = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday',
                    4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
    timestamp = timestamp + ' ' + weekday_dict[datetime_obj.weekday()]
    return timestamp

def check_old_emojis(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        for line, contents in enumerate(file):
            for i in contents:
                if ord(i) > 1000000:
                    with open('conversion/fix_emojis.html', 'a', encoding='utf-8') as fix_file:
                        fix_file.write(i)

def fix_emoji_table(filename):
    char_dict = {}
    contents_error = []
    contents_fixed = []
    with open(filename, 'r', encoding='utf-8') as file:
        for line, contents in enumerate(file):
            if contents.startswith('1; '):
                contents = contents.split('1; ')[1] # ignore first part
                for i in contents:
                    contents_error.append(i)
            elif contents.startswith('2; '):
                contents = contents.split('2; ')[1]
                for i in contents:
                    contents_fixed.append(i)

    for err,fix in zip(contents_error, contents_fixed):
        if err not in char_dict.keys():
            char_dict[err] = fix
    with open('conversion/bad_unicode_fix.txt', 'w', encoding='utf-8') as outfile:
        json.dump(char_dict, outfile)
        #char_dict = json.loads(contents)

def emoji_stats(all_texts, all_users):
    """Emojis starts at int('1f600',16)
    counts all chars that fall in this range for each message"""
    # Make dict for each user, smiley and value
    emoji_dict = {}
    emoji_total_dict = {}
    for user, text in zip(all_users, all_texts):
        for char in text:
            if char in emoji_module.UNICODE_EMOJI or ord(char) > 128512:  # <3 seems to be under 128512
                if not user in emoji_dict.keys():
                    emoji_dict[user] = {}
                if not char in emoji_dict[user].keys():
                    emoji_dict[user][char] = 0
                if not char in emoji_total_dict.keys():
                    emoji_total_dict[char] = 0

                emoji_dict[user][char] += 1
                emoji_total_dict[char] += 1

    sorted_values, sorted_emojis = zip(*sorted(zip(emoji_total_dict.values(),
                                            emoji_total_dict.keys()),
                                        reverse=True))
    most_used_emojis = sorted_emojis[:20]  # 20 most used
    return emoji_dict, most_used_emojis

def count_words(all_texts):
    amount_of_words = 0
    for text in all_texts:
        word_list = text.split(' ')
        amount_of_words += len(word_list)

    return amount_of_words

def unique(list_of_things):
    """Util, debug this!!
    Problem: Set function inbuilt does NOT keep order...
    Solution: Make function yourself that does this"""
    unique_list = []
    for item in list_of_things:
        if item not in unique_list:
            unique_list.append(item)
    return unique_list

def plot_emoji_stats(emoji_dict, most_used_emojis):
    data = []
    for user in emoji_dict.keys():
        y = []
        for emoji in most_used_emojis:
            if emoji in emoji_dict[user].keys():
                y.append(emoji_dict[user][emoji])
            else: # Bug could happen if one user has not written emoji. This should fix it
                y.append(0)
        bar_object = go.Bar(x=most_used_emojis,
                            y=y,
                            name=user)
        data.append(bar_object)
    layout = go.Layout(barmode='stack',
                       width=plot_width,
                       height=plot_height,
                       title='Emoji stats',
                       titlefont = dict(
                            size=26)
                       )
    fig = go.Figure(data=data, layout=layout)
    plotly.offline.plot(fig, filename='results/emoji_stats.html', auto_open=False)

def plot_text_frequency_full(all_texts, all_timestamps, all_users):
    #Only get day, ignore time
    all_timestamps_copy = list(all_timestamps)  # I need to deep-copy list, list() will do it
    for index, timestamp in enumerate(all_timestamps_copy):  # Fix dates
            timestamp = timestamp.split(' ')
            timestamp = ' '.join(timestamp[:1])  # Ignore weekday, join to string
            timestamp = datetime.datetime.strptime(timestamp, "%Y-%m-%d")  # Make into time object
            all_timestamps_copy[index] = timestamp  # Overwrite and make to datetime object

    data = []
    for user in set(all_users):
        all_timestamps_fixed = []
        all_texts_fixed = []
        #pdb.set_trace()
        for timestamp in unique(all_timestamps_copy):
            amount_of_texts = 0
            indices = [i for i, x in enumerate(all_timestamps_copy) if x == timestamp]
            all_timestamps_fixed.append(timestamp)
            for index in indices:
                if user in all_users[index]:
                    amount_of_texts += 1
            all_texts_fixed.append(amount_of_texts)

        bar_object = go.Bar(x=all_timestamps_fixed,
                            y=all_texts_fixed,
                            name=user)
        data.append(bar_object)

    layout = go.Layout(barmode='stack',
                       title='Text stats',
                       width=plot_width,
                       height=plot_height,
                       titlefont=dict(
                           size=26),
                       yaxis=dict(title='Texts')
                       )
    fig = go.Figure(data=data, layout=layout)
    plotly.offline.plot(fig, filename='results/texts_stats_full.html', auto_open=False)

def plot_text_frequency_day(all_texts, all_timestamps, all_users):

    #Only get day, ignore time
    all_timestamps_copy = list(all_timestamps)  # I need to deep-copy list, list() will do it
    for index, timestamp in enumerate(all_timestamps_copy):  # Fix dates
            timestamp = timestamp.split(' ')
            timestamp = timestamp[2]  # Get weekday
            all_timestamps_copy[index] = timestamp  # Overwrite and make to datetime object

    sort_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    all_timestamps_copy = sorted(all_timestamps_copy, key=sort_order.index)  # Sort day correct
    data = []
    for user in set(all_users):
        all_timestamps_fixed = []
        all_texts_fixed = []
        for timestamp in unique(all_timestamps_copy):
            amount_of_texts = 0
            indices = [i for i, x in enumerate(all_timestamps_copy) if x == timestamp]
            all_timestamps_fixed.append(timestamp)
            for index in indices:
                if user in all_users[index]:
                    amount_of_texts += 1
            all_texts_fixed.append(amount_of_texts)

        bar_object = go.Bar(x=all_timestamps_fixed,
                            y=all_texts_fixed,
                            name=user)
        data.append(bar_object)

    layout = go.Layout(barmode='stack',
                       title='Text stats',
                       width=plot_width,
                       height=plot_height,
                       titlefont=dict(
                           size=26),
                       yaxis=dict(title='Texts')
                       )
    fig = go.Figure(data=data, layout=layout)
    plotly.offline.plot(fig, filename='results/texts_stats_day.html', auto_open=False)


def plot_text_frequency_hour(all_texts, all_timestamps, all_users):

    #Only get day, ignore time
    all_timestamps_copy = list(all_timestamps)  # I need to deep-copy list, list() will do it
    for index, timestamp in enumerate(all_timestamps_copy):  # Fix dates
            timestamp = timestamp.split(' ')
            timestamp = timestamp[1]  # Remove seconds
            timestamp = timestamp.split(':')  # Get time
            if int(timestamp[1]) < 15: # No way to round... round to closest half hour
                timestamp[1] = '00'
            elif int(timestamp[1]) < 30:
                timestamp[1] = '30'
            elif int(timestamp[1]) < 45:
                timestamp[1] = '30'
            elif int(timestamp[1]) < 60:
                timestamp[1] = '00'
                timestamp[0] = str(int(timestamp[0]) + 1)
                if timestamp[0] == '24':
                    timestamp[0] = '00'
            timestamp = ':'.join(timestamp[:2])
            timestamp = '2012-12-12 ' + timestamp + ':00'  # Need date in correct format to sort
            all_timestamps_copy[index] = timestamp  # Overwrite and make to datetime object

    data = []
    for user in set(all_users):
        all_timestamps_fixed = []
        all_texts_fixed = []
        for timestamp in unique(all_timestamps_copy):
            amount_of_texts = 0
            indices = [i for i, x in enumerate(all_timestamps_copy) if x == timestamp]
            all_timestamps_fixed.append(timestamp)
            for index in indices:
                if user in all_users[index]:
                    amount_of_texts += 1
            all_texts_fixed.append(amount_of_texts)
        bar_object = go.Bar(x=all_timestamps_fixed,
                            y=all_texts_fixed,
                            name=user)
        data.append(bar_object)
    layout = go.Layout(barmode='stack',
                       title='Text stats',
                       width=plot_width,
                       height=plot_height,
                       titlefont=dict(
                           size=26),
                       yaxis=dict(title='Texts')
                       )
    fig = go.Figure(data=data, layout=layout)
    plotly.offline.plot(fig, filename='results/texts_stats_hour.html', auto_open=False)



def plot_pie_chart(all_texts, all_users):

    # Message count per user
    labels = []
    values_messages = []
    values_word_count = []
    for user in set(all_users):
        labels.append(user)
        values_messages.append(all_users.count(user))

        words_user = 0
        for index, u in enumerate(all_users):
            if u == user:
                words_user += len(all_texts[index].split(' '))
        values_word_count.append(words_user)

    data = [{
            "values": values_messages,
            "labels": labels,
            "domain": {"x": [0, .48]},
            "name": "Messages",
            "hole": .4,
            "type": "pie"
            },
            {
            "values": values_word_count,
            "labels": labels,
            "domain": {"x": [.52, 1]},
            "name": "Word count",
            "hole": .4,
            "type": "pie"
            }]
    layout = go.Layout(title='Piecharts',
                       width=plot_width,
                       height=plot_height,
                       titlefont=dict(size=26),
                       yaxis=dict(title='Texts'),
                       annotations=[{"showarrow": False,
                                    "text": "Messages",
                                    "x": 0.20,
                                    "y": 0.5},
                                    {
                                    "showarrow": False,
                                    "text": "Words",
                                    "x": 0.8,
                                    "y": 0.5
                                    }]
                       )
    fig = go.Figure(data=data, layout=layout)
    plotly.offline.plot(fig, filename='results/piechart.html', auto_open=False)

if __name__ == "__main__":
    import tkinter
    from tkinter.filedialog import askopenfilename
    root = tkinter.Tk()
    root.withdraw()
    print('Please choose a file')
    filename = askopenfilename(initialdir = "data",title = "Select file")
    root.destroy()
    if filename == "":
        print('Nothing choosen. Quitting program')
        quit()
    all_texts, all_users, all_timestamps, total_call_time = get_messages(filename)

    # Get data
    emoji_dict, most_used_emojis = emoji_stats(all_texts, all_users)

    # Use data
    amount_of_words = count_words(all_texts)
    delta_days = (datetime.datetime.now() - datetime.datetime.strptime(all_timestamps[-1].split(' ')[0], "%Y-%m-%d")).days

    #Prints
    print("You have been in touch since:",
          all_timestamps[-1],
          " which is ",
          delta_days,
          " days from today")
    print("You have sent: {} messages".format(len(all_texts)))
    print("Average messages per day: {}".format(round(len(all_texts)/delta_days),3))
    print("Total word count: {}".format(amount_of_words))
    print("Average word count per message: {}".format(round((amount_of_words/len(all_texts)), 2)))
    print("You have called for: {} minutes".format(round(total_call_time, 2)))
    print('')
    print('Plotting data')

    # Plotting
    plot_emoji_stats(emoji_dict, most_used_emojis)
    plot_text_frequency_full(all_texts, all_timestamps, all_users)
    plot_text_frequency_day(all_texts, all_timestamps, all_users)
    plot_text_frequency_hour(all_texts, all_timestamps, all_users)
    plot_pie_chart(all_texts, all_users)

    print('DONE!!')



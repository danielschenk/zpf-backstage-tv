from lxml import html
import re

def parse_program_az(az_html, session):
    tree = html.fromstring(az_html)
    acts = tree.xpath("//div[contains(concat(' ', @class, ' '), ' act ')]")
    programme = {}
    act_number = 1
    for act in acts:
        img = act.find("figure/picture//img")
        a = act.find("figure/figcaption/a")
        actinfo = {}
        actinfo['name'] = a.text
        actinfo['url'] = a.get('href')
        actinfo['img_src'] = img.get('data-src')

        print u'getting and parsing page for act {}/{} "{}"'.format(act_number, len(acts), actinfo['name'])
        act_html = session.get(actinfo['url']).content
        tree_act = html.fromstring(act_html)
        div_playdate = tree_act.xpath(
            "//div[@class='playDate']")
        div_content = tree_act.xpath(
            "//div[contains(concat(' ', @class, ' '), ' content ')]")

        if div_playdate and div_content:
            paragraphs = []
            for element in div_content[0].iter():
                if element.tag.lower() == 'p':
                    # get the contents of this <p> element as-is, ie. a string with all child elements unparsed
                    text = u''.join([element.text if element.text else ''] + [html.tostring(e) for e in element.getchildren()])
                    paragraphs.append(text)

            actinfo['description'] = '<p>' + '</p><p>'.join(paragraphs) + '</p>'
            actinfo['stage'] = div_playdate[0].findall("span")[1].text

            act_shows = []
            days = tree_act.xpath(
                "//span[contains(concat(' ', @class, ' '), ' day ')]")
            if days:
                for day in days:
                    act_shows.append(dict(day=day.text))

                times = tree_act.xpath(
                    "//span[contains(concat(' ', @class, ' '), ' time ')]")
                if times:
                    time_idx = 0
                    for time in times:
                        act_shows[time_idx].update(dict(showtime=time.text.split(' ')[0],
                                                        end=time.text.rsplit(' ')[2]))
                        time_idx += 1
                else:
                    print u'no time found for {}'.format(actinfo['name'])
            else:
                print u'no day found for {}'.format(actinfo['name'])

            country_and_genre = tree_act.xpath(
                "//span[contains(concat(' ', @class, ' '), ' countryAndGenre ')]")
            if country_and_genre:
                text = country_and_genre[0].text
                match = re.match('\((\S+)\)\s*([\w ]+)', text, flags=re.UNICODE)
                if match:
                    actinfo['country'] = match.group(1)
                    actinfo['genre'] = match.group(2).rstrip()
                else:
                    print u'no country and genre found for {}'.format(actinfo['name'])
            else:
                print u'no country and genre found for {}'.format(actinfo['name'])

            for show in act_shows:
                show_key = u'{}_{}_{}'.format(actinfo['name'], show['day'], show['showtime'])
                show.update(actinfo)
                programme[show_key] = show
        else:
            print u'unexpected structure in page of act "{}", skipping'.format(actinfo['name'])

        act_number += 1

    return programme

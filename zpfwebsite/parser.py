import bs4
import re
from . import errors


def parse_program_block_diagram(html, session, day, stage=None):
    programme = {}

    soup = bs4.BeautifulSoup(html, features="lxml")
    stage_rows = soup.find_all("div", class_="border-dashed")
    if not stage_rows:
        raise errors.ZpfWebsiteError("no stage rows found")

    for row in stage_rows:
        stage_name = row.find("div", class_="translate-y-stage-name").text
        if stage is not None and stage != stage_name:
            continue

        acts = row.find_all("div", class_="flex-auto")
        if not acts:
            raise errors.ZpfWebsiteError("no acts found")

        for act in acts:
            link = act.find("a")
            name = link.text

            if name not in programme:
                entry = programme[name] = {"shows": []}
                entry["name"] = name
                entry["url"] = link["href"]

                print(f'getting and parsing page for act "{entry["name"]}"')
                act_html = session.get(entry["url"]).content
                soup_act = bs4.BeautifulSoup(act_html, features="lxml")
                paragraphs = soup_act.find_all("p")
                entry["description"] = "\n\n".join(p.text for p in paragraphs)
                entry["description_html"] = "".join(str(p) for p in paragraphs)
            else:
                entry = programme[name]

            info_text = act.find("span", class_="text-sm").text
            time_text = info_text.splitlines()[1].strip().replace('"', '')
            start, end = [t.strip() for t in time_text.split("-", maxsplit=1)]
            entry["shows"].append({"day": day, "start": start, "end": end})

    return programme


def parse_program_az(az_html, session, stage=None):
    """DEPRECATED, parsing overview page doesn't give multiple show times per act"""

    soup = bs4.BeautifulSoup(az_html, features="lxml")
    acts = soup.find_all("div", class_=re.compile("program-card-."))
    if not len(acts):
        raise errors.ZpfWebsiteError("No acts found")

    programme = {}
    act_number = 1
    for act in acts:
        actinfo = {}
        actinfo["name"] = act.find("h2").text.strip()
        actinfo["stage"] = act.find("span", class_="bottom-0").text.strip()
        if stage is not None and stage != actinfo["stage"]:
            continue

        top_spans = act.find("div", class_="items-start").find_all("span")
        if len(top_spans) == 2:
            day_span, time_span = top_spans[0], top_spans[1]
            actinfo["day"] = day_span.text.strip().lower()
            times = time_span.text.split("-", maxsplit=1)
            assert len(times) == 2, time_span
            actinfo["start"], actinfo["end"] = times[0].strip(), times[1].strip()
        else:
            print(f'warning: act {actinfo["name"]} does not have 2 top spans, cannot determine act time')

        actinfo["url"] = act.find("a")["href"]

        img = act.find("img", class_="lazyloaded")
        if img:
            actinfo["img_src"] = img["srcset"]

        print(f'getting and parsing page for act {act_number} "{actinfo["name"]}"')
        act_html = session.get(actinfo['url']).content
        soup_act = bs4.BeautifulSoup(act_html, features="lxml")
        actinfo["description"] = "\n\n".join(p.text for p in soup_act.find_all("p"))

        programme[actinfo["name"]] = actinfo

        act_number += 1

    return programme

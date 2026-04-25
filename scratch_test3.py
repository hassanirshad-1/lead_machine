from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader("src/dashboard/templates"))
template = env.get_template("leads.html")

try:
    rendered = template.render(leads=[], campaigns=[], current_campaign_id=None, current_status=None, current_search="", current_min_score=0)
    print("Length:", len(rendered))
except Exception as e:
    import traceback
    traceback.print_exc()

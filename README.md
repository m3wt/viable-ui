### Viable

Viable is a fork of [Vial](https://get.vial.today/), an open-source cross-platform (Windows, Linux and Mac) GUI for configuring your keyboard in real time.

# Getting started

Download the latest release from the [Releases](https://github.com/viable-kb/gui/releases) page.

For Linux udev rules, follow the instructions at [get.vial.today/manual/linux-udev.html](https://get.vial.today/manual/linux-udev.html).

# Development

Python 3.12+ recommended.

Install dependencies:

```
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-test.txt
```

To launch the application:

```
source venv/bin/activate
export PYTHONPATH="src/main/python:$PYTHONPATH"
python src/main/python/main.py
```

To run tests:

```
pytest src/main/python/test/ -v
```

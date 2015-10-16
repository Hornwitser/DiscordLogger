import sys
import json
import logging
import collections

import pymysql

def partition(direction, data):
    if direction == 0: # client receive
        if 't' in data:
            return data['t']
        else:
            return data['op']
    else:
        return None

def analyze(row, result):
    try:
        d = json.loads(row['raw'])
    except json.decoder.JSONDecodeError:
        print("error decoding", row['id'], file=sys.stderr)
        return

    part = partition(row['dir'], d)
    if part is None:
        return

    sub_analyze(result[part], d)

def sub_analyze(node, leaf):
    node['count'] = node.get('count', 0) + 1

    t = type(leaf).__name__
    node['types'][t] = node['types'].get(t, 0) + 1

    if t == 'dict':
        for k, v in leaf.items():
            sub_analyze(node['nodes'][k], v)
    elif t == 'list':
        for v in leaf:
            sub_analyze(node['leafs'], v)
    elif t == 'str':
        if 'charset' in node:
            node['charset'].update(list(leaf))
        elif len(node['values']) > 10:
            node['charset'] = set(list(leaf))
            for k in list(node['values'].keys()):
                if type(k) == str:
                    node['charset'].update(list(k))
        else:
            node['values'][leaf] = node['values'].get(leaf, 0) + 1

    elif t == 'int':
        if 'min' in node:
            node['min'] = min(node['min'], leaf)
            node['max'] = max(node['max'], leaf)
        elif len(node['values']) > 10:
            values = [v for v in node['values'] if type(v) == int]
            node['min'] = min(values)
            node['max'] = max(values)
        else:
            node['values'][leaf] = node['values'].get(leaf, 0) + 1
    elif t == 'bool' or t == 'NoneType':
        node['values'][leaf] = node['values'].get(leaf, 0) + 1
    else:
        raise ValueError("Unknown type %" % t)

header = """<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <title>Discord WebSocket Log</title>

        <!-- At least it's better than unstyled HTML... -->
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>

        <style>
            @media (min-width: 768px) {
                #query-box {
                    width: calc(100% - 12em);
                }
                #query-box > input {
                    width: 100%;
                }

                #query-button {
                    width: 11em;
                }

                form {
                    margin-bottom: 2em;
                }
            }

            code {
                color: black;
                background: inherit;
                white-space: pre;
            }
        </style>
    </head>
    <body>
        <div class="container-fluid">
            <h1>Discord WebSocket Analysis</h1>
            <p>An analysis of the messages on the discord WebSocket, for API debugging and reference purpose.
"""

footer = """        </div>
    </body>
</head>
"""

def post_analyze(result):
    print(header)

    indent = '    '*3
    for name, part in result.items():
        print('{dt}<div class="panel panel-default">\n'
              '{dt}    <div class="panel-heading">\n'
              '{dt}        <h3 class="panel-title">{title}</h3>\n'
              '{dt}    </div>\n'
              '{dt}    <div class="panel-body">'
              ''.format(dt=indent, title=name))

        print('<code>', end='')
        node_analyze(part, part['count'])
        print('</code>')

        print('{dt}    </div>\n'
              '{dt}</div>'.format(dt=indent))

    print(footer)

def node_analyze(node, top_count, indent=''):
    if 'dict' in node['types']:
        print('{</code><br>')
        for k, v in node['nodes'].items():
            sub_indent = ''.join(['    ', indent])
            print('<code>{}"{}": '.format(sub_indent, k), end='')
            node_analyze(v, top_count, sub_indent)
            print('</code><br>')
        print('<code>{}}}'.format(indent), end='')
    elif 'list' in node['types']:
        sub_indent = ''.join(['    ', indent])
        print('[</code><br>\n<code>{}'.format(sub_indent), end='')
        node_analyze(node['leafs'], node['count'], sub_indent)
        print(',</code><br>\n'
              '<code>{}...</code><br>\n'
              '<code>{}]'.format(sub_indent, indent), end='')
    else:
        print(json.dumps(node['types'], cls=SetEncoder), end='')
        return
        ValueError("Unkown type %s" % node['types'])

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return ''.join(sorted(obj))
        else:
            return json.JSONEncoder.default(self, obj)

def defaultdict_factory():
    return collections.defaultdict(defaultdict_factory)

if __name__ == '__main__':
    global connection
    config = eval(open('config').read())
    logging.basicConfig(level=logging.INFO)
    connection = pymysql.connect(host=config['db_host'],
                                 user=config['db_user'],
                                 password=config['db_password'],
                                 db=config['db_schema'],
                                 charset='utf8mb4',
                                 cursorclass=pymysql.cursors.DictCursor)

    with connection.cursor() as cursor:
        sql = "SELECT id, dir, raw FROM message"
        cursor.execute(sql)

        result = defaultdict_factory()

        while True:
            row = cursor.fetchone()
            if row is None:
                break
            analyze(row, result)

        post_analyze(result)

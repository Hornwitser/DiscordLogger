import sys
import json
import logging
import collections
import html

import pymysql

def partition(direction, data):
    if direction == 0: # client receive
        if 't' in data and data['t'] is not None:
            if data['t'].startswith('CHANNEL') and data['d']['is_private']:
                return '{} {}'.format(data['t'], '(private)')
            elif data['t'] == 'GUILD_DELETE' and data['d'].get('unavailable'):
                return '{} {}'.format(data['t'], '(unavailable)')
            elif data['t'] == 'MESSAGE_UPDATE' and 'content' not in data['d']:
                return '{} {}'.format(data['t'], '(embeds only)')
            else:
                return data['t']
        else:
            return 'OP {}'.format(data['op'])
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

def sub_analyze(node, leaf, snoflake=False):
    node['count'] = node.get('count', 0) + 1

    t = type(leaf).__name__
    node['types'][t] = node['types'].get(t, 0) + 1

    if t == 'dict':
        for k, v in leaf.items():
            sub_analyze(node['nodes'][k], v, k=='guilds')
    elif t == 'list':
        for v in leaf:
            node['leaf_count'] = node.get('leaf_count', 0) + 1
            if snoflake and v.get('unavailable'):
                sub_analyze(node['snowflake_leafs'], v)
            else:
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
            values.append(leaf)
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
        <title>WebSocket Analysis</title>

        <!-- At least it's better than unstyled HTML... -->
        <link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">
        <script src="https://code.jquery.com/jquery-2.1.4.min.js"></script>
        <script src="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min.js"></script>

        <link rel="stylesheet" href="style">
    </head>
    <body>
        <nav class="navbar navbar-default">
            <div class="container">
                <div class="navbar-header">
                    <a class="navbar-brand" href=".">Discord WebSocket Log</a>
                </div>
                <ul class="nav navbar-nav navbar-right">
                    <li><a href=".">Overview</a></li>
                    <li><a href="query">Query Database</a></li>
                    <li class="active"><a href="analysis">Analysis</a></li>
                </ul>
                </div>
            </div>
        </nav>

        <div class="container">
            <p>An analysis of the messages on the discord WebSocket, for API debugging and reference purpose.
"""

footer = """        </div>
        <script>
            jQuery(".infoline").click(function() {
                jQuery(this).find('.infobox').slideToggle();
            });
        </script>
    </body>
</head>
"""

def post_analyze(result):
    print(header)

    indent = '    '*3
    print('{}<h2>Partitions</h2>'.format(indent))
    print('{}<ul>'.format(indent))
    for name in sorted(result.keys()):
        print('{dt}    <li><a href="#{n}">{n}</a></li>'
              ''.format(dt=indent, n=name))
    print('{}</ul>'.format(indent))

    for name in sorted(result.keys()):
        part = result[name]
        print('{dt}<div class="panel panel-default">\n'
              '{dt}    <div class="panel-heading">\n'
              '{dt}        <h3 id="{name}" class="panel-title">{name}{ht}</h3>\n'
              '{dt}    </div>\n'
              '{dt}    <div class="panel-body">'
              ''.format(dt=indent, name=name, ht=headertags(part)))

        print('<pre class="infoblock">', end='')

        lines = flatten_prop(part, part['count'])
        output_node(lines)

        print('</pre>')

        print('{dt}    </div>\n'
              '{dt}</div>'.format(dt=indent))

    print(footer)

def flatten_prop(node, top_count, name=None, indent=''):
    if len(node) == 0:
        raise TypeError("empty node")
    is_obj = 'dict' in node['types']
    is_array = 'list' in node['types']
    if is_obj and is_array:
        raise TypeError("unsupported dual obj, array node")
    elif is_array and name is None:
        raise TypeError("unsupported nested array node")

    lines = []
    data = {k:v for k, v in node.items() if k not in ('nodes', 'leafs')}
    data['top_count'] = top_count
    sub_indent = ''.join([indent, '    '])

    if is_obj:
        if name is None:
            lines = [{'line_type': 'obj_start', 'indent': indent,
                      'data': data}]
            for sub_name in sorted(node['nodes']):
                sub_node = node['nodes'][sub_name]
                lines.extend(flatten_prop(sub_node, node['count'], sub_name,
                                          sub_indent))
            lines.append({'line_type': 'obj_end', 'indent': indent})
        else:
            lines.append({'line_type': 'prop_obj_start', 'name': name,
                          'data': data, 'indent': indent})
            for sub_name in sorted(node['nodes']):
                sub_node = node['nodes'][sub_name]
                lines.extend(flatten_prop(sub_node, node['count'], sub_name,
                                          sub_indent))
            lines.append({'line_type': 'prop_obj_end', 'indent': indent})

    elif is_array:
        if 'snowflake_leafs' in node:
            lines.append({'line_type': 'prop_array_start', 'name': name,
                          'data': data, 'indent': indent})
            lines.extend(flatten_prop(node['snowflake_leafs'],
                         node['leaf_count'], None, sub_indent))
            lines.append({'line_type': 'prop_array_alt', 'indent': indent})
            lines.extend(flatten_prop(node['leafs'], node['leaf_count'], None,
                         sub_indent))
            lines.append({'line_type': 'prop_array_end', 'indent': indent})
        elif 'leafs' in node:
            lines.append({'line_type': 'prop_array_start', 'name': name,
                          'data': data, 'indent': indent})
            lines.extend(flatten_prop(node['leafs'], node['leaf_count'], None,
                         sub_indent))
            lines.append({'line_type': 'prop_array_end', 'indent': indent})
        else:
            lines.append({'line_type': 'prop_empty_array', 'name': name,
                          'data': data, 'indent': indent})

    else:
        if name is None:
            lines.append({'line_type': 'value', 'data': data, 'indent': indent})
        else:
            lines.append({'line_type': 'prop', 'name': name, 'indent': indent,
                          'data': data})

    return lines

def output_node(lines):
    for line in lines:
        t = line['line_type']
        indent = line['indent']
        if t == 'obj_start':
            print('<div class="infoline">{}{{</div>'.format(indent))
        elif t == 'obj_end':
            print('<div class="infoline">{}}}</div>'.format(indent))
        elif t == 'prop_obj_start':
            data = line['data']
            box = infobox(data)
            tags = infotags(data)
            name = line['name']
            if 'values' in data:
                raise ValueError('unhandled dual object, noed in output_node')
            else:
                print('<div class="infoline">'
                          '{}<span class="key">"{}"</span>: {{{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, name, tags, box))
        elif t == 'prop_obj_end':
            print('<div class="infoline">{}}}</div>'.format(indent))
        elif t == 'prop_array_start':
            data = line['data']
            box = infobox(data)
            tags = infotags(data)
            name = line['name']
            if 'values' in data:
                raise ValueError('unhandled dual array object in output_node')
            else:
                print('<div class="infoline">'
                          '{}<span class="key">"{}"</span>: [{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, name, tags, box))
        elif t == 'prop_array_end':
            print('<div class="infoline">{}    ...</div>'.format(indent))
            print('<div class="infoline">{}]</div>'.format(indent))
        elif t == 'prop_array_alt':
            print('<div class="infoline">{}    '
                      '<span class="type-or">or</span>'
                  '</div>'.format(indent))
        elif t == 'prop_empty_array':
            data = line['data']
            box = infobox(data)
            tags = infotags(data)
            name = line['name']
            if 'values' in data:
                raise ValueError('unhandled dual array object in output_node')
            else:
                print('<div class="infoline">'
                          '{}<span class="key">"{}"</span>: []{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, name, tags, box))
        elif t == 'value':
            data = line['data']
            box = infobox(data)
            tags = infotags(data)
            if len(data['values']) == 1:
                value = next(iter(data['values'].keys()))
                print('<div class="infoline">'
                          '{}{}{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, json_value(value), tags,
                                      box))
            else:
                print('<div class="infoline">'
                          '{}{}{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, json_types(data['types']),
                                      tags, box))
        elif t == 'prop':
            data = line['data']
            box = infobox(data)
            tags = infotags(data)
            name = line['name']
            if len(data['values']) == 1:
                value = next(iter(data['values'].keys()))
                print('<div class="infoline">'
                          '{}<span class="key">"{}"</span>: {}{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, name, json_value(value), tags,
                                      box))
            else:
                print('<div class="infoline">'
                          '{}<span class="key">"{}"</span>: {}{}'
                          '<div class="panel panel-default infobox" style="display: none;">'
                              '{}'
                          '</div>'
                      '</div>'.format(indent, name, json_types(data['types']),
                                      tags, box))
        else:
            raise ValueError("Unkown line type '%s'" % t)

def json_value(value):
    t = type(value)
    output = html.escape(json.dumps(value))
    if t == str:
        return '<span class="string">{}</span>'.format(output)
    elif t == float:
        return '<span class="number">{}</span>'.format(output)
    elif t == int:
        return '<span class="int">{}</span>'.format(output)
    elif t == bool:
        return '<span class="bool">{}</span>'.format(output)
    elif value == None:
        return '<span class="null">null</span>'
    else:
        raise TypeError("Unkown json type %s" % t)

def json_types(types):
    list_of_types = []
    for t in types:
        if t == 'str':
            list_of_types.append('<span class="string">"&lt;string&gt;"</span>')
        elif t == 'float':
            list_of_types.append('<span class="number">&lt;number&gt;</span>')
        elif t == 'int':
            list_of_types.append('<span class="int">&lt;integer&gt;</span>')
        elif t == 'bool':
            list_of_types.append('<span class="bool">&lt;boolean&gt;</span>')
        elif t == 'NoneType':
            list_of_types.append('<span class="null">null</span>')
        else:
            raise TypeError("Uknown json type %s" % t)

    return ' <span class="type-or">or</span> '.join(list_of_types)

def headertags(part):
    if part['count'] < 10:
        return ' <span class="label label-danger">very few samples</span>'
    elif part['count'] < 100:
        return ' <span class="label label-warning">few samples</span>'
    else:
        return ''

def infotags(data):
    if data['count'] < data['top_count']:
        return ' <span class="label label-default">optional</span>'
    elif data['count'] > data['top_count']:
        return ' <span class="label label-danger">count error</span>'
    else:
        return ''

def infobox(data):
    sections = []

    text = 'Samples {}'.format(data['count'])
    if data['count'] == data['top_count']:
        text += ', always present.'
    else:
        percent = data['count'] / data['top_count'] * 100
        text += ', present in {:.2f}% of samples'.format(percent)

    sections.append(("Info", text))

    if 'values' not in data:
        pass
        #raise ValueError('infobox data with no values!')
    elif len(data['values']) == 1:
        pass
    elif len(data['values']) < 10:
        section = ''
        for value, count in data['values'].items():
            if count > 1:
                section += ('<li>{} {} times</li>'
                            ''.format(json_value(value), count))
            else:
                section += '<li>{} one time</li>'.format(json_value(value))

        section = '<ul>{}</ul>'.format(section)
        sections.append(("Values Observed", section))
    else:
        section = ''
        for value in data['values']:
            section += '<li>{}</li>'.format(json_value(value))

        section = '<ul>{}</ul>'.format(section)
        sections.append(("Sample Values", section))

    sections = ''.join(['<h4>{}</h4>{}'.format(t, s) for t, s in sections])
    return '<div class="panel-body">{}</div>'.format(sections)

class SetEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, set):
            return ''.join(sorted(obj))
        else:
            return json.JSONEncoder.default(self, obj)

def defaultdict_factory():
    return collections.defaultdict(defaultdict_factory)


if __name__ == '__main__':
    import sys
    import pickle

    if len(sys.argv) < 3:
        print("Usage: {0} prepare {{file}} [WHERE clause] \n"
              "  or:  {0} render {{file}}".format(sys.argv[0]))

    elif sys.argv[1] == 'prepare':
        result_file = open(sys.argv[2], 'wb')
        config = eval(open('config.py').read())
        logging.basicConfig(level=logging.INFO)
        connection = pymysql.connect(host=config['db_host'],
                                     user=config['db_user'],
                                     password=config['db_password'],
                                     db=config['db_schema'],
                                     charset='utf8mb4',
                                     cursorclass=pymysql.cursors.DictCursor)

        where = ' '.join(sys.argv[3:]) if len(sys.argv) > 3 else 'TRUE'
        sql = "SELECT id, dir, raw FROM message WHERE {}".format(where)
        result = defaultdict_factory()

        with connection.cursor() as cursor:
            cursor.execute(sql)

            while True:
                row = cursor.fetchone()
                if row is None:
                    break
                analyze(row, result)

        pickle.dump(result, result_file)
        result_file.close()

    elif sys.argv[1] == 'render':
        result_file = open(sys.argv[2], 'rb')
        result = pickle.load(result_file)
        result_file.close()
        post_analyze(result)

    else:
        print("Uknown operation {}".format(sys.argv[1]))
        exit(1)

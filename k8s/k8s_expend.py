#!/usr/bin/python
import yaml
import os
import sys
import jinja2
import argparse
import re

from jinja2 import Environment, FileSystemLoader, meta


parser = argparse.ArgumentParser(
    description='Script to replace K8s spec vars',
    version='1.0'
    )

parser.add_argument('--env', dest='env')
parser.add_argument('--site', dest='site')
parser.add_argument('--template', dest='template', const='variables.yaml', nargs='?')

args = parser.parse_args()


def open_yaml_file(filename='variables.yaml'):
    """Open and parse yaml file to dict"""
    with open(filename, 'r') as stream:
        try:
            data = yaml.load(stream)
        except yaml.YAMLError as exc:
            print exc
    return data


def get_jinja_vars_from_template(template):
    """Get all Jinja2 variables from template file"""
    path = os.path.dirname(os.path.abspath(__file__))
    template_env = Environment(
        autoescape=False,
        loader=FileSystemLoader(os.path.join(path)),
        trim_blocks=False
    )
    template_source = template_env.loader.get_source(template_env, template)
    parsed_content = template_env.parse(template_source)
    variables = meta.find_undeclared_variables(parsed_content)
    return variables


def build_vars_dict(site, env, vars, template_vars):
    dict = {}
    for var in template_vars:
        if var in vars.get(env, {}).get(site, {}):
            dict[var] = vars[env][site][var]
        elif var in vars.get(site, {}):
            dict[var] = vars[site][var]
        elif var in vars.get(env, {}):
            dict[var] = vars[env][var]
        elif var in vars:
            dict[var] = vars[var]
    dict['site'] = args.site
    dict['env'] = args.env
    if re.match('^(TEST)$', args.env, re.I):
        dict['mlx_envstr'] = '-test'
    elif re.match('^(UAT)$', args.env, re.I):
        dict['mlx_envstr'] = '-uat'
    elif re.match('^(STABLE)$', args.env, re.I):
        dict['mlx_envstr'] = ''
    return dict


def render_template(tpl_path, context):
    path, filename = os.path.split(tpl_path)
    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(path or './')
    ).get_template(filename).render(context)


def check_vars_presence_in_template(template_vars, defined_vars):
    not_define_vars = []
    for var in template_vars:
        if var in defined_vars.keys():
            pass
        else:
            not_define_vars.append(var)
    return not_define_vars


def main():
    user_vars = open_yaml_file(args.template)
    kubernetes_spec = user_vars.get('kubernetes_spec', 'app_template.yaml')
    template_vars = get_jinja_vars_from_template(kubernetes_spec)
    vars_defined = build_vars_dict(args.site, args.env, user_vars, template_vars)
    not_define_vars = check_vars_presence_in_template(template_vars, vars_defined)

    if len(not_define_vars) == 0:
        result = render_template(kubernetes_spec, vars_defined)
        with open('kubernetes.yaml', 'w') as f:
            f.write(result)
    else:
        print "Cannot expand those variables: {}".format(not_define_vars)
        sys.exit(2)


if __name__ == '__main__':
    main()


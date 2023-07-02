from flowpipe import Graph, INode, Node, InputPlug, OutputPlug
from pprint import pprint

graph = Graph(name='My First Graph')



@Node(outputs=['asset'])
def get_assets():
    assets = ['char_elfie_default', 'char_butz_gloves', 'char_bo_default']
    return {f'asset.{i}': v for i, v in enumerate(assets) }

@Node(outputs=['assetname','variant'])
def process_assets(assets):
    _dict = {}
    for i, v in assets.items():
        name, variant = v.rsplit('_',1)
        _dict[f'assetname.{i}'] = name
        _dict[f'variant.{i}'] = variant

    return _dict

@Node()
def done(names, variants):
    for i, v in names.items():
        print(v, variants[i])

# g = get_assets(graph=graph)
# p = process_assets(graph=graph)
# d = done(graph=graph)


# g.outputs['asset'] >> p.inputs['assets']
# p.outputs['assetname'] >> d.inputs['names']
# p.outputs['variant'] >> d.inputs['variants']


# graph.evaluate()


for i in range(0, 30, 10):
    print(i)


# @Node()
# def Party(attendees):
#     print('{0} and {1} are having a great party!'.format(
#         ', '.join(list(attendees.values())[:-1]), list(attendees.values())[-1]))

# @Node(outputs=['people'])
# def InvitePeople(amount):
#     people = ['John', 'Jane', 'Mike', 'Michelle']
#     d = {'people.{0}'.format(i): people[i] for i in range(amount)}
#     d['people'] = {people[i]: people[i] for i in range(amount)}
#     pprint(d)
#     return d

# invite = InvitePeople(graph=graph, amount=4)
# birthday_party = Party(graph=graph, name='Birthday Party')
# invite.outputs['people'] >> birthday_party.inputs['attendees']

# print(graph.name)
# print(graph)
# graph.evaluate()

# graph.evaluate(mode='threading')  # Options are linear, threading and multiprocessing

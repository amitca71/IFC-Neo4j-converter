import IfcOpenShell
import sys
from py2neo import Graph, Node
import time


class IfcTypeDict(dict):
    def __missing__(self, key):
        value = self[key] = IfcOpenShell.create_entity(
            key).wrapped_data.get_attribute_names()
        return value


# ifc_path = "ifc_files/IfcOpenHouse_original.ifc"
ifc_path = "ifc_files/191225_TE-Bld_zone_GEO.ifc"
start = time.time()  # Culculate time to process
print("Start!")
print(time.strftime("%Y/%m/%d %H:%M", time.strptime(time.ctime())))

typeDict = IfcTypeDict()

assert typeDict["IfcWall"] == (
    'GlobalId',
    'OwnerHistory',
    'Name',
    'Description',
    'ObjectType',
    'ObjectPlacement',
    'Representation',
    'Tag')

nodes = []
edges = []

ourLabel = 'test'

f = IfcOpenShell.open(ifc_path)

for el in f:
    if el.is_a() == "IfcOwnerHistory":
        continue
    tid = el.id()
    cls = el.is_a()
    pairs = []
    keys = []
    try:
        keys = [x for x in el.get_info() if x not in ["type", "id", "OwnerHistory"]]
    except RuntimeError:
        # we actually can't catch this, but try anyway
        pass
    for key in keys:
        val = el[key]
        if any(hasattr(val, "is_a") and val.is_a(thisTyp)
               for thisTyp in ["IfcBoolean", "IfcLabel", "IfcText", "IfcReal"]):
            val = val.wrappedValue
        if val and type(val) is tuple and type(val[0]) in (str, bool, float, int):
            val = ",".join(str(x) for x in val)
        if type(val) not in (str, bool, float, int):
            continue
        pairs.append((key, val))
    nodes.append((tid, cls, pairs))

    for i in range(len(el)):
        try:
            el[i]
        except RuntimeError as e:
            if str(e) != "Entity not found":
                print("ID", tid, e, file=sys.stderr)
            continue
        if isinstance(el[i], IfcOpenShell.entity_instance):
            if el[i].is_a() == "IfcOwnerHistory":
                continue
            if el[i].id() != 0:
                # edges.append({"from":tid, "to":el[i].id(), "reltype":typeDict[cls][i]})
                edges.append((tid, el[i].id(), typeDict[cls][i]))
                continue
        try:
            iter(el[i])
        except TypeError:
            continue
        destinations = [
            x.id() for x in el[i] if isinstance(
                x, IfcOpenShell.entity_instance)]
        for connectedTo in destinations:
            # edges.append({"from": tid, "to": connectedTo, "reltype": typeDict[cls][i]})
            edges.append((tid, connectedTo, typeDict[cls][i]))

if len(nodes) == 0:
    print("no nodes in file", file=sys.stderr)
    sys.exit(1)

print("List creat prosess done. Take for ", time.time() - start)
print(time.strftime("%Y/%m/%d %H:%M", time.strptime(time.ctime())))

# Initialize neo4j database
graph = Graph(auth=('neo4j', 'Neo4j'))  # http://localhost:7474
graph.delete_all()

graph.run("CREATE INDEX ON :IfcNode(ClassName, nid)")

for node in nodes:
    nId, cls, pairs = node
    one_node = Node("IfcNode", ClassName=cls, nid=nId)
    for k, v in pairs:
        one_node[k] = v
    graph.create(one_node)

print("Node creat prosess done. Take for ", time.time() - start)
print(time.strftime("%Y/%m/%d %H:%M", time.strptime(time.ctime())))

# json = {"jsondoc": edges}

# query = """
# WITH {json} AS document
# UNWIND document.jsondoc AS jsondoc
# UNWIND jsondoc AS row
# MATCH (a),(b)
# WHERE a.nid = row.to AND b.nid = row.from
# CALL apoc.create.relationship(a,row.reltype,{},b) YIELD rel
# RETURN *
# """
# graph.run(query, json=json)

for (nId1, nId2, relType) in edges:
    graph.run(
        "MATCH (a),(b) WHERE a.nid = {:d} AND b.nid = {:d} CREATE (a)-[r:{:s}]->(b)".format(
            nId1,
            nId2,
            relType))

print("All done. Take for ", time.time() - start)
print(time.strftime("%Y/%m/%d %H:%M", time.strptime(time.ctime())))

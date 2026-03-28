import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st
import folium
from streamlit_folium import st_folium
import osmnx as ox

# -------------------------------
# 1. DATA EXTRACTION (OSM)
# -------------------------------
ox.settings.overpass_endpoint = "https://overpass.kumi.systems/api/interpreter"

place = "Lucknow, Uttar Pradesh, India"
tags = {"power": ["substation", "line"]}
gdf = ox.features_from_place(place, tags)

# Voltage filter
if "voltage" in gdf.columns:
    gdf = gdf[gdf["voltage"].notnull()]
    gdf = gdf[gdf["voltage"].astype(str).str.contains("132|220|400", na=False)]

substations = gdf[gdf["power"] == "substation"]
lines = gdf[gdf["power"] == "line"]

# -------------------------------
# 2. CREATE NODES (from coordinates)
# -------------------------------
edges_list = []

for _, line in lines.iterrows():
    if line.geometry.geom_type == "LineString":
        coords = list(line.geometry.coords)
        for j in range(len(coords) - 1):
            edges_list.append({
                "bus0": coords[j],
                "bus1": coords[j+1]
            })

edges = pd.DataFrame(edges_list)
edges.to_csv("edges.csv", index_label="Line")
print("Edges CSV preview:")
print(edges.head()) 

# Convert coordinates → node IDs (CRITICAL FIX)
all_coords = list(set(edges["bus0"]).union(set(edges["bus1"])))
coord_to_id = {coord: i for i, coord in enumerate(all_coords)}

edges["bus0"] = edges["bus0"].map(coord_to_id)
edges["bus1"] = edges["bus1"].map(coord_to_id)

# Create nodes dataframe
nodes = pd.DataFrame({
    "bus": list(coord_to_id.values()),
    "x": [c[0] for c in coord_to_id.keys()],
    "y": [c[1] for c in coord_to_id.keys()]
}).set_index("bus")
nodes.to_csv("nodes.csv", index_label="bus")
print("Nodes CSV preview:")
print(nodes.head())

# -------------------------------
# 3. BUILD GRAPH (TUTORIAL CORE)
# -------------------------------
N = nx.from_pandas_edgelist(edges, "bus0", "bus1")
print(N)

# -------------------------------
# 4. ANALYSIS (PURE NETWORKX)
# -------------------------------
degrees = [val for _, val in N.degree()]
avg_degree = np.mean(degrees)
pd.Series(nx.degree_histogram(N)).plot.bar()
plt.xlabel("Degree(number of connections)")
plt.ylabel("Number of nodes")
plt.show()

components = list(nx.connected_components(N))
num_components = len(components)

is_planar = nx.is_planar(N)

cycles = nx.cycle_basis(N)
num_cycles = len(cycles)
cycle_lengths = [len(c) for c in cycles]

# -------------------------------
# 5. POSITION MAPPING (IMPORTANT)
# -------------------------------
pos = nodes.apply(lambda row: (row["x"], row["y"]), axis=1).to_dict()

print("Number of nodes:", N.number_of_nodes())
print("Number of edges:", N.number_of_edges())
print("Is planar?", nx.is_planar(N))
print("Connected components:", len(list(nx.connected_components(N))))
print("Avergae degree:", np.mean([deg for _, deg in N.degree]))

A = nx.adjacency_matrix(N, weight=None).todense()
print("Adjacency matrix shape:", A.shape)

I = nx.incidence_matrix(N, oriented=True).todense()
print("Incidence matrix shape:", I.shape)

L = nx.laplacian_matrix(N).todense()
print("Laplacian matrix shape:", L.shape)

print("Number of cycles:", len(cycles))
cycle_lengths = [len(c) for c in cycles]
plt.hist(cycle_lengths, bins=20)
plt.xlabel("Cycle length (edges)")
plt.ylabel("Frequency")
plt.show()
print("Average cycle length:", np.mean(cycle_lengths))

subgraphs = [N.subgraph(c).copy() for c in nx.connected_components(N)]
colors = ["red", "blue", "green", "orange", "teal", "cyan", "black"]

plt.figure(figsize=(10,10))
for i, sub in enumerate(subgraphs):
    sub_nodes_with_pos = [n for n in sub.nodes if n in pos]
    sub_pos = {k: pos[k] for k in sub_nodes_with_pos}
    nx.draw(sub.subgraph(sub_nodes_with_pos), pos=sub_pos, node_size=5, edge_color=colors[i % len(colors)])
plt.title("Subgraphs of India Power Network")
plt.show()

# -------------------------------
# 6. STREAMLIT APP
# -------------------------------
st.title("⚡ Power Grid Topology (Lucknow)")

st.write("### Graph Statistics")
st.write(f"Nodes: {N.number_of_nodes()}")
st.write(f"Edges: {N.number_of_edges()}")
st.write(f"Connected Components: {num_components}")
st.write(f"Average Degree: {avg_degree:.2f}")
st.write(f"Is Planar: {is_planar}")
st.write(f"Cycles: {num_cycles}")
st.write("Adjacency shape:", A.shape)
st.write("Incidence shape:", I.shape)
st.write("Laplacian shape:", L.shape)
# -------------------------------
# 7. DEGREE DISTRIBUTION
# -------------------------------
st.write("### Degree Distribution")

fig1, ax1 = plt.subplots()
pd.Series(nx.degree_histogram(N)).plot.bar(ax=ax1)
ax1.set_xlabel("Degree")
ax1.set_ylabel("Number of Nodes")
st.pyplot(fig1)

# -------------------------------
# 8. CYCLE LENGTH DISTRIBUTION
# -------------------------------
st.write("### Cycle Length Distribution")

fig2, ax2 = plt.subplots()
ax2.hist(cycle_lengths, bins=20)
ax2.set_xlabel("Cycle Length")
ax2.set_ylabel("Frequency")
st.pyplot(fig2)

# -------------------------------
# 9. NETWORK VISUALIZATION
# -------------------------------
st.write("### Network Graph")

fig3, ax3 = plt.subplots(figsize=(8, 8))
nx.draw(N, pos=pos, node_size=5, ax=ax3)
st.pyplot(fig3)

# -------------------------------
# 10. MAP VISUALIZATION
# -------------------------------
st.write("### Geographic Map")

m = folium.Map(location=[26.8467, 80.9462], zoom_start=10)

# Draw edges
for _, row in edges.iterrows():
    coord1 = pos[row["bus0"]]
    coord2 = pos[row["bus1"]]

    folium.PolyLine(
        locations=[(coord1[1], coord1[0]), (coord2[1], coord2[0])],
        color="blue",
        weight=1,
        opacity=0.5
    ).add_to(m)

# Draw nodes
for i, row in nodes.iterrows():
    folium.CircleMarker(
        location=[row["y"], row["x"]],
        radius=2,
        color="red",
        fill=True
    ).add_to(m)

st_folium(m, width=1000, height=600)
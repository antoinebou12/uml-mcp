import base64
import zlib
from enum import Enum

# Define the reserved keywords
simple_reserved_keywords = {
    "label",
    "desc",
    "shape",
    "icon",
    "constraint",
    "tooltip",
    "link",
    "near",
    "width",
    "height",
    "direction",
    "top",
    "left",
    "right",
    "bottom",
    "grid-rows",
    "grid-columns",
    "grid-gap",
    "vertical-gap",
    "horizontal-gap",
    "class",
    "linevars",
}

reserved_keyword_holders = {
    "style",
    "source-arrowhead",
    "target-arrowhead",
}

composite_reserved_keywords = {
    "classes",
    "constraint",
    "label",
    "icon",
    "layers",
    "scenarios",
    "steps",
}

style_keywords = {
    "opacity",
    "stroke",
    "fill",
    "fill-pattern",
    "stroke-width",
    "stroke-dash",
    "border-radius",
    "font",
    "font-size",
    "font-color",
    "bold",
    "italic",
    "underline",
    "text-transform",
    "shadow",
    "multiple",
    "double-border",
    "3d",
    "animated",
    "filled",
}

reserved_keywords = set(
    simple_reserved_keywords
    | style_keywords
    | composite_reserved_keywords
    | reserved_keyword_holders
)

# Compression dictionary originally derived from "-><--<->" + sorted(reserved_keywords).
compression_dict = "-><---<->3danimatedboldborder-radiusclassclassesconstraintdescdirectiondouble-borderfillfill-patternfilledfontfont-colorfont-sizegrid-columnsgrid-gapgrid-rowsheighthorizontal-gapiconitaliclabellayersleftlinkmultiplenearopacityscenariosshadowshapesource-arrowheadstepsstrokestroke-dashstroke-widthstyletarget-arrowheadtext-transformtooltiptopunderlinevarsvertical-gapwidth"


class Layout(Enum):
    DAGRE = "dagre"
    ELK = "elk"
    TALA = "tala"


class Theme(Enum):
    DEFAULT = "0"
    DARK = "103"


def encode(raw: str) -> str:
    # Convert the raw string to bytes
    raw_bytes = raw.encode("utf-8")

    # Compress the bytes using the compression dictionary
    compressor = zlib.compressobj(
        wbits=-zlib.MAX_WBITS, zdict=compression_dict.encode("utf-8")
    )
    compressed_bytes = compressor.compress(raw_bytes) + compressor.flush()

    # Encode the compressed bytes as base64
    encoded_bytes = base64.b64encode(compressed_bytes)

    return encoded_bytes.decode("utf-8")


def decode(encoded: str) -> str:
    # Decode the base64 string to bytes
    encoded_bytes = base64.urlsafe_b64decode(encoded)

    # Decompress the bytes using the compression dictionary
    decompressor = zlib.decompressobj(
        wbits=-zlib.MAX_WBITS, zdict=compression_dict.encode("utf-8")
    )
    decompressed_bytes = decompressor.decompress(encoded_bytes) + decompressor.flush()

    return decompressed_bytes.decode("utf-8")


def generate_d2graphviz_url(edge_def, layout=Layout.DAGRE, theme=Theme.DEFAULT):
    encoded_edge_def = encode(edge_def)
    return f"https://play.d2lang.com/?script={encoded_edge_def}&layout={layout.value}&theme={theme.value}"


if __name__ == "__main__":
    edge_def = """
timeline mixer: "" {
  explanation: |md
    ## **Timeline mixer**
    - Inject ads, who-to-follow, onboarding
    - Conversation module
    - Cursoring,pagination
    - Tweat deduplication
    - Served data logging
  |
}
People discovery: "People discovery \nservice"
admixer: Ad mixer {
  style.fill: "#c1a2f3"
}

onboarding service: "Onboarding \nservice"
timeline mixer -> People discovery
timeline mixer -> onboarding service
timeline mixer -> admixer
container0: "" {
  graphql
  comment
  tlsapi
}
container0.graphql: GraphQL\nFederated Strato Column {
  shape: image
  icon: https://upload.wikimedia.org/wikipedia/commons/thumb/1/17/GraphQL_Logo.svg/1200px-GraphQL_Logo.svg.png
}
container0.comment: |md
  ## Tweet/user content hydration, visibility filtering
|
container0.tlsapi: TLS-API (being deprecated)
container0.graphql -> timeline mixer
timeline mixer <- container0.tlsapi
twitter fe: "Twitter Frontend " {
  icon: https://icons.terrastruct.com/social/013-twitter-1.svg
  shape: image
}
twitter fe -> container0.graphql: iPhone web
twitter fe -> container0.tlsapi: HTTP Android
web: Web {
  icon: https://icons.terrastruct.com/azure/Web%20Service%20Color/App%20Service%20Domains.svg
  shape: image
}

Iphone: {
  icon: 'https://ss7.vzw.com/is/image/VerizonWireless/apple-iphone-12-64gb-purple-53017-mjn13ll-a?$device-lg$'
  shape: image
}
Android: {
  icon: https://cdn4.iconfinder.com/data/icons/smart-phones-technologies/512/android-phone.png
  shape: image
}

web -> twitter fe
timeline scorer: "Timeline\nScorer" {
  style.fill: "#ffdef1"
}
home ranker: Home Ranker

timeline service: Timeline Service
timeline mixer -> timeline scorer: Thrift RPC
timeline mixer -> home ranker: {
  style.stroke-dash: 4
  style.stroke: "#000E3D"
}
timeline mixer -> timeline service
home mixer: Home mixer {
  # style.fill: "#c1a2f3"
}
container0.graphql -> home mixer: {
  style.stroke-dash: 4
  style.stroke: "#000E3D"
}
home mixer -> timeline scorer
home mixer -> home ranker: {
  style.stroke-dash: 4
  style.stroke: "#000E3D"
}
home mixer -> timeline service
manhattan 2: Manhattan
gizmoduck: Gizmoduck
socialgraph: Social graph
tweetypie: Tweety Pie
home mixer -> manhattan 2
home mixer -> gizmoduck
home mixer -> socialgraph
home mixer -> tweetypie
Iphone -> twitter fe
Android -> twitter fe
prediction service2: Prediction Service {
  shape: image
  icon: https://cdn-icons-png.flaticon.com/512/6461/6461819.png
}
home scorer: Home Scorer {
  style.fill: "#ffdef1"
}
manhattan: Manhattan
memcache: Memcache {
  icon: https://d1q6f0aelx0por.cloudfront.net/product-logos/de041504-0ddb-43f6-b89e-fe04403cca8d-memcached.png
}

fetch: Fetch {
  style.multiple: true
  shape: step
}

feature: Feature {
  style.multiple: true
  shape: step
}
scoring: Scoring {
  style.multiple: true
  shape: step
}
fetch -> feature
feature -> scoring

prediction service: Prediction Service {
  shape: image
  icon: https://cdn-icons-png.flaticon.com/512/6461/6461819.png
}
scoring -> prediction service
fetch -> container2.crmixer

home scorer -> manhattan: ""

home scorer -> memcache: ""
home scorer -> prediction service2
home ranker -> home scorer
home ranker -> container2.crmixer: Candidate Fetch
container2: "" {
  style.stroke: "#000E3D"
  style.fill: "#ffffff"
  crmixer: CrMixer {
    style.fill: "#F7F8FE"
  }
  earlybird: EarlyBird
  utag: Utag
  space: Space
  communities: Communities
}
etc: ...etc

home scorer -> etc: Feature Hydration

feature -> manhattan
feature -> memcache
feature -> etc: Candidate sources
"""
    url = generate_d2graphviz_url(edge_def, layout=Layout.ELK, theme=Theme.DARK)
    print("Generated URL:", url)

    encoded = "vFdtb9s4Ev6uXzFwWvQuiN5sN0mFwx1yadMUaLHe2rv9UmBBiyOZrUSqJGUn3ea_L4aSbFl2usUusPkQkzPkzMNnXkhZUSIpoBR3qBMYjeB3DwDvqoJJRkwm8K3kHgDAyQmcni72NpyeOo0Pb-QnTC0wbs5gs1K-VX6mikJtzkDJpWKaC5m3a6-VXKM2zjqUitcFdppaG6WFzM8qlovGf6tabJBZ4MjrqhBpXzNHvUYOnFkGhcrzxtE378GboaoKBC5Mqtao7xMYDUXwURrUa5HiyGO8JeGKN6dzVDiiA0qZBEYnaczG2WTkPXje7lzQmkhg9NNO2LO8zzL4_4UhjiNLDu0fWdRi9lJKRyFRR9sY5ppVqy-FB5CqskRpPQBbGFYJ76G3PmjXJfCaBj-__ShvkKOmyoO51cwquHbl0NBB6ZqAKFlOUaPkT2BlbWWSMKyrQjEebMRnUSIXLFA6D2lW0SwkHEqa0K7qchnGYXwRtj5_e6tyFZh1HsbjKKru_KE8qGS-D7s9VJeeJyeUImjD2qAGWofSwuqea5crZ7AWRixFIew9ZKKwSGnmfetbbMhJYPF27l_N3sC_lkjkc6w0pkTHv4_QRkHYD8swSv_x4cCJZzeCWhFklDSLdnKjHWwOTQD3uaWZCSxqzYzVdWqJgdCoVLAijOKJ35r0Y-JrGKmHnkeCfCz-YrZSEmGDy8cXdxzdLhYzuJJcK8G9DS4T-IDLH0bNvtYaww-4fDqO5k1uPx1H19SHw6uq2pO-VCUT0hw_lPemIsxJz_OzzrUxF8H668Y5FCZ0W8Jf0bXuD0JjgcaErKoK9IWz4sdj_3yaL_2q1iR9PoniC7_8JONJUfjsf084Eia_yJ88O4TSkpEcISHlchqQKBPUiB0ialcNO6Epmba-g2B8i-lKqkLlAk34PB6HrLHb6F0ZHLKwwaXLw23UdjloUqVdY-8a90c5d6LRke6WZRyzmLrbSpUImsnPtPeWJu_dxOtZ7pre9kqYP9qmDuAsVlpkFt7Pro-s3nO-Q9m7CROYDsQEP4qiV5OXBP97CFqQzknb8G-3Y-fu5NGmf7z--6b-EtydgSNkDbR_n5zHvLXElEyumLVMwjiBd93Ey8VXuqvTzwm87oZe034cFQnM3aS5dzxLzfi-EpQfbggzgQPXPU8DzdbZQN7zNzxG569tCYN6aKtzIK00cuHei93pxwnMdsI2of_84ku59F0x-5XMg6xglmau0KmGz6fnsft3Gb9obzKHvqsGl39NWX63KreE9QNTYpmydIUJvGtHR1oQj7-cZxHD4i6qlA7SQtU8o-smkGjDShPZ1i9UrkzIMZrGz6OpH3G-9KeT7NxfXr5AP8NoOo0macouud955e15vAxtukrghn56h-gewAlYXeOOR3rhNtuYrTXSRjf48a1EnpB54oiji_qHdzqolAqt8w6Ey7DGmHckN_6p1GghEJpDEDvw2140DlLdvDz6WbVXYPQoPNRuE2c0GuqOVEb_Ttg2on6L2qkOoSVwzSQXnFlsUmTXSsfbF-tjLeuwIOiP5Dvr-t22fQ-X31zcXN68ouUP9GnDdHG_FJon8IqG_xea3o-1ZXkCv1jm7teKUbjn9NO-n2sprECTwPVu4j14aNMEgiBAmx7w63RdWt92L1Gvn23bAO0J27j0Zc7WjsLme9F4fwQAAP__&"
    decoded = decode(encoded)
    print(decoded)

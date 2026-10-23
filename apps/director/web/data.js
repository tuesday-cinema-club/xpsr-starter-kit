// Fixed data: roles, the two workshop clients, the kit's shot vocabulary and
// the seven audit checks. Client facts match workshop-build/client-briefs/.

export const ROLES = [
  { id: "director", label: "Director", phone: true },
  { id: "writer", label: "Writer", phone: false },
  { id: "previs", label: "Previs", phone: true },
  { id: "frames", label: "Frames", phone: false },
  { id: "editsound", label: "Edit & Sound", phone: true },
  { id: "auditor", label: "Auditor", phone: true },
];

export const PRESETS = {
  ember: {
    label: "Ember & Oak Coffee",
    kicker: "Client A",
    client: "Ember & Oak Coffee",
    project_title: "Second Shop Launch",
    ask: "A neighborhood micro-roaster opening its second shop wants a 30-second launch spot for social media and the shop's window screen.",
    tone: ["Grounded", "Warm", "Communal", "Made by hand"],
    facts: [
      ["SRC-001", "Ember & Oak roasts in small batches in the back room of its original shop."],
      ["SRC-002", "The second shop is opening in the same neighborhood, a short walk from the first."],
      ["SRC-003", "Every bag is labelled with the roast date."],
      ["SRC-004", "The founder buys green coffee from two importers who publish their farm partners."],
    ],
    bible: "templates/ember-and-oak-bible.json",
    locations: [["roastery", "Original roastery, back room"], ["new_shop", "Second shop, front counter"]],
    characters: [["roaster", "The Roaster"], ["regular", "The Regular"]],
  },
  spoke: {
    label: "Spoke Co-op",
    kicker: "Client B",
    client: "Spoke Co-op",
    project_title: "Open Hours Recruitment",
    ask: "A volunteer-run bike-repair co-op wants a 30-second recruitment spot for community boards and social media.",
    tone: ["Energetic", "Gritty", "Inclusive", "Empowering"],
    facts: [
      ["SRC-001", "Volunteers teach members to repair their own bikes; they do not repair bikes for you."],
      ["SRC-002", "Members can use the shared tool wall and repair stands during open hours."],
      ["SRC-003", "Parts are sold at cost; labor and teaching are free for members."],
      ["SRC-004", "New members join by attending one open-hours session."],
    ],
    bible: "templates/spoke-coop-bible.json",
    locations: [["workshop", "Co-op workshop floor"]],
    characters: [["mechanic", "Volunteer Mechanic"], ["newcomer", "Newcomer"]],
  },
  custom: {
    label: "Custom pitch",
    kicker: "Your own",
    client: "",
    project_title: "",
    ask: "Your own client. Add each fact you will claim, with an id, before you cite it.",
    tone: [],
    facts: [],
    bible: "",
    locations: [["location_1", "Main location"]],
    characters: [],
  },
};

export const FRAMINGS = ["Extreme Wide", "Wide", "Medium", "Close Up", "Extreme Close Up"];
export const MOVES = ["Static", "Push In", "Pull Out", "Pan Left", "Pan Right", "Tilt Up", "Tilt Down", "Handheld"];
export const LENSES = [16, 24, 35, 50, 85, 100, 135];

export const DEFAULT_SHOTS = [
  { label: "Establishing", framing: "Wide", lens_mm: 24, camera_move: "Push In" },
  { label: "Kinetic action", framing: "Close Up", lens_mm: 50, camera_move: "Handheld" },
  { label: "Hero lock", framing: "Medium", lens_mm: 35, camera_move: "Static" },
];

export const CHECKS = [
  { n: 1, id: "intent", name: "Intent", ask: "Honors the brief and every exclusion", gate: true },
  { n: 2, id: "evidence", name: "Evidence", ask: "Every claim cites a row in research_log.csv" },
  { n: 3, id: "continuity", name: "Continuity", ask: "Faces, wardrobe, set and light match from shot to shot" },
  { n: 4, id: "specificity", name: "Specificity", ask: "Nothing generic; could only be this client" },
  { n: 5, id: "techqc", name: "Technical QC", ask: "Resolution, frame rate, runtime, loudness, peaks" },
  { n: 6, id: "provenance", name: "Provenance", ask: "Every asset has a row in provenance.csv" },
  { n: 7, id: "signature", name: "Human signature", ask: "A named human reviewed, changed and approved it", gate: true },
];

export const LOCAL_FRAME_MODEL = "ComfyUI/flux-2-klein-4b.safetensors";

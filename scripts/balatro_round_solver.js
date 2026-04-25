#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DEFAULT_CARD_VALUES = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11];
const HAND_NAMES = [
  "Flush Five",
  "Flush House",
  "Five of a Kind",
  "Straight Flush",
  "Four of a Kind",
  "Full House",
  "Flush",
  "Straight",
  "Three of a Kind",
  "Two Pair",
  "Pair",
  "High Card",
];

const RANK_INDEX = {
  "2": 0,
  "3": 1,
  "4": 2,
  "5": 3,
  "6": 4,
  "7": 5,
  "8": 6,
  "9": 7,
  "10": 8,
  "Jack": 9,
  "Queen": 10,
  "King": 11,
  "Ace": 12,
};

const SUIT_INDEX = {
  "Hearts": 0,
  "Clubs": 1,
  "Diamonds": 2,
  "Spades": 3,
};

const EDITION_INDEX = {
  "None": 0,
  "Foil": 1,
  "Holo": 2,
  "Holographic": 2,
  "Polychrome": 3,
  "Negative": 4,
};

const ENHANCEMENT_INDEX = {
  "none": 0,
  "bonus": 1,
  "mult": 2,
  "wild": 3,
  "glass": 4,
  "steel": 5,
  "stone": 6,
  "gold": 7,
  "lucky": 8,
};

const SEAL_INDEX = {
  "None": 0,
  "Gold": 1,
  "Red": 2,
  "Blue": 3,
  "Purple": 4,
};

function parseArgs() {
  const args = process.argv.slice(2);
  const options = { samples: 96, beam: 18 };
  for (let i = 0; i < args.length; i += 1) {
    if (args[i] === "--samples" && args[i + 1]) {
      options.samples = Math.max(8, Number(args[i + 1]) || options.samples);
      i += 1;
    } else if (args[i] === "--beam" && args[i + 1]) {
      options.beam = Math.max(6, Number(args[i + 1]) || options.beam);
      i += 1;
    }
  }
  return options;
}

function readStdin() {
  return fs.readFileSync(0, "utf8");
}

function hashString(input) {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < input.length; i += 1) {
    h ^= input.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mixSeed(baseSeed, label) {
  return hashString(`${baseSeed >>> 0}|${label}`);
}

function mulberry32(seed) {
  let a = seed >>> 0;
  return function rand() {
    a = (a + 0x6D2B79F5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffleInPlace(array, rand) {
  for (let i = array.length - 1; i > 0; i -= 1) {
    const j = Math.floor(rand() * (i + 1));
    const tmp = array[i];
    array[i] = array[j];
    array[j] = tmp;
  }
}

function chooseSample(array, count, rand) {
  const clone = array.slice();
  shuffleInPlace(clone, rand);
  return clone.slice(0, count);
}

function seedCardSignature(card) {
  return `${card.id}|${card.rank}|${card.suit}|${card.enhancement || "None"}|${card.edition || "None"}|${card.seal || "None"}`;
}

function roundStateSignature(roundState) {
  return JSON.stringify({
    currentScore: roundState.currentScore,
    targetScore: roundState.targetScore,
    handsLeft: roundState.handsLeft,
    discardsLeft: roundState.discardsLeft,
    handSize: roundState.handSize,
    hand: roundState.hand.map(seedCardSignature).sort(),
    deckCount: roundState.deck.length,
    discardCount: roundState.discardPile.length,
  });
}

function normalizeEnhancement(value) {
  const lower = String(value || "None").toLowerCase();
  if (lower.includes("bonus")) return "bonus";
  if (lower.includes("mult")) return "mult";
  if (lower.includes("wild")) return "wild";
  if (lower.includes("glass")) return "glass";
  if (lower.includes("steel")) return "steel";
  if (lower.includes("stone")) return "stone";
  if (lower.includes("gold")) return "gold";
  if (lower.includes("lucky")) return "lucky";
  return "none";
}

function makeCalculator() {
  const repoRoot = path.resolve(__dirname, "..");
  const breakdownPath = path.join(repoRoot, "_third_party", "balatro-calculator", "breakdown.js");
  const cardsPath = path.join(repoRoot, "_third_party", "balatro-calculator", "cards.js");
  if (!fs.existsSync(breakdownPath) || !fs.existsSync(cardsPath)) {
    throw new Error("Missing _third_party/balatro-calculator. The exact round solver cannot run.");
  }

  const cardsSource = fs.readFileSync(cardsPath, "utf8");
  const jokerNameToIndex = new Map();
  for (const line of cardsSource.split(/\r?\n/)) {
    const orderMatch = line.match(/order\s*=\s*(\d+)/);
    const nameMatch = line.match(/name\s*=\s*["']([^"']+)["']/);
    if (orderMatch && nameMatch) {
      jokerNameToIndex.set(nameMatch[1], Number(orderMatch[1]) - 1);
    }
  }

  const context = {
    console,
    chipc: "",
    multc: "",
    prodc: "x",
    probc: "",
    endc: "",
    rankNames: ["2", "3", "4", "5", "6", "7", "8", "9", "10", "Jack", "Queen", "King", "Ace"],
    suitNames: ["Hearts", "Clubs", "Diamonds", "Spades"],
    hands: HAND_NAMES.map((name) => ({ name })),
  };
  vm.createContext(context);
  vm.runInContext(`${fs.readFileSync(breakdownPath, "utf8")}\nthis.Hand = Hand;`, context);
  return { Hand: context.Hand, jokerNameToIndex };
}

const CALC = makeCalculator();

function buildApproxDeck(state) {
  const signatures = new Set();
  for (const card of [...(state.hand || []), ...(state.deck || []), ...(state.discard_pile || [])]) {
    signatures.add(`${card.rank}|${card.suit}`);
  }

  const deck = [];
  const ranks = Object.keys(RANK_INDEX);
  const suits = Object.keys(SUIT_INDEX);
  let index = 0;
  for (const rank of ranks) {
    for (const suit of suits) {
      const signature = `${rank}|${suit}`;
      if (!signatures.has(signature)) {
        deck.push({
          id: `sim_${index}`,
          rank,
          suit,
          base_chips: DEFAULT_CARD_VALUES[RANK_INDEX[rank]],
          enhancement: "None",
          edition: "None",
          seal: "None",
          is_debuffed: false,
        });
        index += 1;
      }
    }
  }
  return deck;
}

function cardSignature(card) {
  return `${card.id}|${card.rank}|${card.suit}|${card.enhancement || "None"}|${card.edition || "None"}|${card.seal || "None"}`;
}

function encodeCard(card) {
  const rank = RANK_INDEX[card.rank] ?? 0;
  const suit = SUIT_INDEX[card.suit] ?? 0;
  const edition = EDITION_INDEX[card.edition || "None"] ?? 0;
  const enhancement = ENHANCEMENT_INDEX[normalizeEnhancement(card.enhancement)] ?? 0;
  const seal = SEAL_INDEX[card.seal || "None"] ?? 0;
  const defaultChips = DEFAULT_CARD_VALUES[rank];
  const extraChips = Math.max(0, (card.base_chips ?? defaultChips) - defaultChips);
  return [rank, suit, edition, enhancement, seal, extraChips, Boolean(card.is_debuffed), 0, 0];
}

function extractNumeric(value, fallback = 0) {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const match = value.match(/-?\d+(\.\d+)?/);
    if (match) return Number(match[0]);
  }
  return fallback;
}

function jokerValue(state, joker) {
  const internal = joker.internal_state || {};
  const name = joker.name || "";
  switch (name) {
    case "Banner":
      return state.economy?.discards_left || 0;
    case "Mystic Summit":
      return state.economy?.discards_left || 0;
    case "Blue Joker":
      return (state.deck || []).length;
    case "Bull":
      return state.economy?.money || 0;
    case "Acrobat":
      return (state.economy?.hands_left || 0) === 1 ? 1 : 0;
    case "Green Joker":
    case "Ride the Bus":
    case "Square Joker":
    case "Runner":
    case "Castle":
    case "Flash Card":
    case "Fortune Teller":
    case "Popcorn":
    case "Spare Trousers":
    case "Ice Cream":
    case "Ramen":
    case "Constellation":
    case "Hologram":
    case "Campfire":
    case "Lucky Cat":
    case "Vampire":
    case "Obelisk":
      return extractNumeric(internal.mult ?? internal.chips ?? internal.Xmult ?? internal.x_mult ?? internal.extra, 0);
    case "Loyalty Card":
      return extractNumeric(internal.remaining, 1) <= 0 ? 0 : 1;
    default:
      return extractNumeric(internal.mult ?? internal.chips ?? internal.Xmult ?? internal.x_mult, 0);
  }
}

function encodeJoker(state, joker) {
  const jokerId = CALC.jokerNameToIndex.get(joker.name);
  if (jokerId === undefined) return null;
  const edition = EDITION_INDEX[joker.edition || "None"] ?? 0;
  return [jokerId, jokerValue(state, joker), edition, Boolean(joker.is_debuffed), joker.sell_value || 0];
}

function deriveLevel(handName, info) {
  if (info && Number.isFinite(info.level) && info.level > 0) {
    return info.level;
  }
  return 1;
}

function buildHandsArray(handLevels) {
  return HAND_NAMES.map((name) => {
    const info = handLevels?.[name] || {};
    return [
      deriveLevel(name, info),
      Number.isFinite(info.planets) ? info.planets : 0,
      Number.isFinite(info.played) ? info.played : 0,
      Number.isFinite(info.played_this_round) ? info.played_this_round : 0,
    ];
  });
}

function bigintLikeToNumber(score) {
  if (!Number.isFinite(score.mantissa) || !Number.isFinite(score.exponent)) return Number.MAX_VALUE;
  if (score.exponent > 300) return Number.MAX_VALUE;
  return score.mantissa * (10 ** score.exponent);
}

function compareScore(a, b) {
  if (a.exponent !== b.exponent) return a.exponent - b.exponent;
  if (a.mantissa !== b.mantissa) return a.mantissa - b.mantissa;
  return 0;
}

function evaluatePlay(state, fullHand, playedCards) {
  const playedSignatures = new Set(playedCards.map(cardSignature));
  const heldCards = fullHand.filter((card) => !playedSignatures.has(cardSignature(card)));
  const encodedJokers = (state.jokers || []).map((joker) => encodeJoker(state, joker)).filter(Boolean);
  const hand = new CALC.Hand({
    cards: playedCards.map(encodeCard),
    cardsInHand: heldCards.map(encodeCard),
    jokers: encodedJokers,
    hands: buildHandsArray(state.hand_levels),
    TheFlint: state.blind?.name === "The Flint",
    TheEye: state.blind?.name === "The Eye",
    breakdown: false,
  });
  hand.compileAll();
  const result = hand.simulateBestHand();
  return {
    mantissa: result[0],
    exponent: result[1],
    chips: result[2],
    mult: result[3],
    numeric: bigintLikeToNumber({ mantissa: result[0], exponent: result[1] }),
  };
}

function combinations(array, minSize, maxSize) {
  const results = [];
  const n = array.length;
  const limit = Math.min(maxSize, n);
  function helper(start, combo, target) {
    if (combo.length === target) {
      results.push(combo.slice());
      return;
    }
    for (let i = start; i <= n - (target - combo.length); i += 1) {
      combo.push(array[i]);
      helper(i + 1, combo, target);
      combo.pop();
    }
  }
  for (let size = minSize; size <= limit; size += 1) {
    helper(0, [], size);
  }
  return results;
}

function evaluateAllPlays(state, hand) {
  const combos = combinations(hand, 1, Math.min(5, hand.length));
  return combos.map((combo) => {
    const score = evaluatePlay(state, hand, combo);
    return {
      action: "PLAY_HAND",
      cards: combo.map((card) => card.id),
      score,
      size: combo.length,
      rankSum: combo.reduce((sum, card) => sum + (RANK_INDEX[card.rank] ?? 0), 0),
    };
  }).sort((left, right) => {
    const cmp = compareScore(right.score, left.score);
    if (cmp !== 0) return cmp;
    if (left.size !== right.size) return left.size - right.size;
    return left.rankSum - right.rankSum;
  });
}

function discardHeuristic(card) {
  let value = (RANK_INDEX[card.rank] ?? 0) * 2;
  if (normalizeEnhancement(card.enhancement) !== "none") value += 6;
  if ((card.edition || "None") !== "None") value += 4;
  if ((card.seal || "None") !== "None") value += 3;
  if (card.rank === "Ace" || card.rank === "King" || card.rank === "Queen" || card.rank === "Jack") value += 3;
  return value;
}

function candidateDiscards(state, hand, beam) {
  const subsets = combinations(hand, 1, Math.min(5, hand.length));
  return subsets.map((subset) => ({
    action: "DISCARD",
    cards: subset.map((card) => card.id),
    heuristic: subset.reduce((sum, card) => sum + discardHeuristic(card), 0),
    size: subset.length,
  })).sort((left, right) => {
    if (left.heuristic !== right.heuristic) return left.heuristic - right.heuristic;
    if (left.size !== right.size) return left.size - right.size;
    return left.cards.join("|").localeCompare(right.cards.join("|"));
  }).slice(0, Math.max(4, Math.floor(beam / 2)));
}

function cloneState(roundState) {
  return {
    currentScore: roundState.currentScore,
    targetScore: roundState.targetScore,
    handsLeft: roundState.handsLeft,
    discardsLeft: roundState.discardsLeft,
    handSize: roundState.handSize,
    hand: roundState.hand.map((card) => ({ ...card })),
    deck: roundState.deck.map((card) => ({ ...card })),
    discardPile: roundState.discardPile.map((card) => ({ ...card })),
  };
}

function drawToHand(roundState, rand) {
  while (roundState.hand.length < roundState.handSize) {
    if (roundState.deck.length === 0) {
      if (roundState.discardPile.length === 0) break;
      roundState.deck = roundState.discardPile.splice(0);
      shuffleInPlace(roundState.deck, rand);
    }
    if (roundState.deck.length === 0) break;
    roundState.hand.push(roundState.deck.shift());
  }
}

function applyAction(state, action, rand) {
  const next = cloneState(state);
  const chosen = new Set(action.cards);
  const selectedCards = next.hand.filter((card) => chosen.has(card.id));
  next.hand = next.hand.filter((card) => !chosen.has(card.id));

  if (action.action === "PLAY_HAND") {
    const playScore = evaluatePlay(action.baseState, [...selectedCards, ...next.hand], selectedCards);
    next.currentScore += playScore.numeric;
    next.handsLeft -= 1;
    next.discardPile.push(...selectedCards);
  } else {
    next.discardsLeft -= 1;
    next.discardPile.push(...selectedCards);
  }

  drawToHand(next, rand);
  return next;
}

function terminalUtility(roundState) {
  const cleared = roundState.currentScore >= roundState.targetScore;
  const slack = roundState.currentScore - roundState.targetScore;
  if (cleared) {
    return 100000 + roundState.handsLeft * 700 + roundState.discardsLeft * 350 - Math.max(0, slack) * 0.02;
  }
  const progress = roundState.targetScore > 0 ? roundState.currentScore / roundState.targetScore : 0;
  return -100000 + progress * 4000 + roundState.handsLeft * 120 + roundState.discardsLeft * 80;
}

function rolloutPolicy(baseState, roundState, beam, rand, seedToken) {
  while (roundState.currentScore < roundState.targetScore && roundState.handsLeft > 0) {
    const plays = evaluateAllPlays(baseState, roundState.hand);
    const bestPlay = plays[0];
    if (!bestPlay) break;
    const remainingTarget = Math.max(0, roundState.targetScore - roundState.currentScore);
    const targetPressure = remainingTarget / Math.max(1, bestPlay.score.numeric);

    if (bestPlay.score.numeric + roundState.currentScore >= roundState.targetScore || roundState.discardsLeft <= 0 || roundState.handsLeft <= 1) {
      return { action: "PLAY_HAND", cards: bestPlay.cards };
    }

    const discardOptions = candidateDiscards(baseState, roundState.hand, Math.max(6, Math.floor(beam / 2)));
    let bestDiscard = null;
    let bestDiscardGain = 0;
    for (const discard of discardOptions) {
      const testState = cloneState(roundState);
      const chosen = new Set(discard.cards);
      const discarded = testState.hand.filter((card) => chosen.has(card.id));
      testState.hand = testState.hand.filter((card) => !chosen.has(card.id));
      testState.discardPile.push(...discarded);
      testState.discardsLeft -= 1;
      const branchSeed = mixSeed(seedToken, `discard|${discard.cards.join(",")}|${roundState.currentScore}`);
      const branchRand = mulberry32(branchSeed);
      drawToHand(testState, branchRand);
      const followUpPlay = evaluateAllPlays(baseState, testState.hand)[0];
      if (!followUpPlay) continue;
      const gain = followUpPlay.score.numeric - bestPlay.score.numeric;
      if (gain > bestDiscardGain) {
        bestDiscardGain = gain;
        bestDiscard = discard;
      }
    }

    const discardThreshold = Math.max(6, bestPlay.score.numeric * (targetPressure > 1.7 ? 0.08 : 0.14));
    if (bestDiscard && bestDiscardGain > discardThreshold) {
      return { action: "DISCARD", cards: bestDiscard.cards };
    }

    return { action: "PLAY_HAND", cards: bestPlay.cards };
  }
  return null;
}

function evaluateRootAction(baseState, rootRoundState, action, sampleCount, beam, seedBase) {
  const returns = [];
  let clears = 0;
  const actionSeed = mixSeed(seedBase, `${action.action}|${action.cards.join(",")}`);
  for (let sample = 0; sample < sampleCount; sample += 1) {
    const sampleSeed = mixSeed(actionSeed, `sample|${sample}`);
    const rand = mulberry32(sampleSeed);
    let current = applyAction(rootRoundState, { ...action, baseState }, rand);
    let depth = 0;
    while (current.currentScore < current.targetScore && current.handsLeft > 0) {
      const policySeed = mixSeed(sampleSeed, `depth|${depth}|${roundStateSignature(current)}`);
      const nextAction = rolloutPolicy(baseState, current, beam, rand, policySeed);
      if (!nextAction) break;
      current = applyAction(current, { ...nextAction, baseState }, rand);
      if (current.discardsLeft < 0) break;
      depth += 1;
    }
    if (current.currentScore >= current.targetScore) clears += 1;
    returns.push(terminalUtility(current));
  }
  returns.sort((a, b) => a - b);
  const mean = returns.reduce((sum, value) => sum + value, 0) / Math.max(1, returns.length);
  const variance = returns.reduce((sum, value) => sum + ((value - mean) ** 2), 0) / Math.max(1, returns.length);
  const standardError = Math.sqrt(variance) / Math.sqrt(Math.max(1, returns.length));
  const confidence = 1.96 * standardError;
  const lowerIndex = Math.floor(0.2 * Math.max(0, returns.length - 1));
  const lowerQuantile = returns[lowerIndex] ?? mean;
  const clearProb = clears / Math.max(1, returns.length);
  return {
    mean,
    variance,
    standardError,
    confidence,
    lowerQuantile,
    clearProb,
    sampleCount: returns.length,
    value: mean + 0.35 * lowerQuantile,
  };
}

function buildRootState(state) {
  return {
    currentScore: state.blind.current_score || 0,
    targetScore: state.blind.target_score || 0,
    handsLeft: state.economy.hands_left || 0,
    discardsLeft: state.economy.discards_left || 0,
    handSize: state.economy.hand_size || (state.hand || []).length || 8,
    hand: (state.hand || []).map((card) => ({ ...card })),
    deck: (state.deck && state.deck.length ? state.deck : buildApproxDeck(state)).map((card) => ({ ...card })),
    discardPile: (state.discard_pile || []).map((card) => ({ ...card })),
  };
}

function chooseRootAction(state, options) {
  const roundState = buildRootState(state);
  const plays = evaluateAllPlays(state, roundState.hand);
  if (plays.length === 0) {
    return {
      action: "NO_OP",
      message: "No playable combinations",
      diagnostics: {
        solver: "js_round_solver",
        reason: "no_playable_combinations",
        options,
      },
    };
  }

  const target = roundState.targetScore - roundState.currentScore;
  const lethalPlays = plays.filter((play) => play.score.numeric >= target);
  if (lethalPlays.length > 0) {
    lethalPlays.sort((left, right) => {
      if (left.size !== right.size) return left.size - right.size;
      const cmp = compareScore(right.score, left.score);
      if (cmp !== 0) return cmp;
      return left.rankSum - right.rankSum;
    });
    return {
      action: "PLAY_HAND",
      cards: lethalPlays[0].cards,
      diagnostics: {
        solver: "js_round_solver",
        reason: "lethal_play_found",
        chosen_play: {
          cards: lethalPlays[0].cards,
          score: lethalPlays[0].score.numeric,
          size: lethalPlays[0].size,
        },
        immediate_top_plays: plays.slice(0, 5).map((play) => ({
          cards: play.cards,
          score: play.score.numeric,
          size: play.size,
        })),
        options,
      },
    };
  }

  const rootActions = [
    ...plays.slice(0, options.beam).map((play) => ({ action: "PLAY_HAND", cards: play.cards })),
  ];

  if (roundState.discardsLeft > 0) {
    rootActions.push(...candidateDiscards(state, roundState.hand, options.beam));
  }

  const seedBase = hashString(JSON.stringify({
    seed: state.meta?.seed || "RL_Balatro",
    round: state.meta?.round || 0,
    ante: state.meta?.ante || 0,
    stake: state.meta?.stake || 0,
    phase: state.meta?.phase || "",
    current_score: state.blind?.current_score || 0,
    target_score: state.blind?.target_score || 0,
    hands_left: state.economy?.hands_left || 0,
    discards_left: state.economy?.discards_left || 0,
    hand: (state.hand || []).map(seedCardSignature).sort(),
    deckCount: (state.deck || []).length,
    discardCount: (state.discard_pile || []).length,
    jokers: (state.jokers || []).map((joker) => `${joker.id}|${joker.name}|${joker.edition || "None"}`).sort(),
  }));

  const initialSamples = Math.min(options.samples, Math.max(12, Math.floor(options.samples / 3)));
  const refineTopK = Math.max(2, Math.min(4, Math.floor(options.beam / 3)));
  const scoredActions = [];
  for (const action of rootActions) {
    const stats = evaluateRootAction(state, roundState, action, initialSamples, options.beam, seedBase);
    const scored = { ...action, stats };
    scoredActions.push(scored);
  }

  scoredActions.sort((left, right) => right.stats.value - left.stats.value);
  const leader = scoredActions[0];
  const refinePool = [];
  for (const candidate of scoredActions) {
    if (refinePool.length >= refineTopK) break;
    const closeClearProb = (leader.stats.clearProb - candidate.stats.clearProb) <= 0.12;
    const closeMean = (leader.stats.mean - candidate.stats.mean) <= Math.max(25, leader.stats.confidence + candidate.stats.confidence);
    if (closeClearProb || closeMean) {
      refinePool.push(candidate);
    }
  }
  if (refinePool.length === 0) {
    refinePool.push(...scoredActions.slice(0, refineTopK));
  }

  if (options.samples > initialSamples) {
    for (const candidate of refinePool) {
      candidate.stats = evaluateRootAction(state, roundState, candidate, options.samples, options.beam, seedBase);
    }
  }

  scoredActions.sort((left, right) => right.stats.value - left.stats.value);
  const best = scoredActions[0];

  return {
    action: best.action,
    cards: best.cards,
    diagnostics: {
      solver: "js_round_solver",
      reason: "risk_adjusted_rollout_search",
      seed_base: seedBase,
      sampling_plan: {
        initial_samples: initialSamples,
        refined_samples: options.samples,
        refine_top_k: refineTopK,
        sampling_method: "successive_refinement_with_state_seeded_rollouts",
      },
      immediate_top_plays: plays.slice(0, 5).map((play) => ({
        cards: play.cards,
        score: play.score.numeric,
        size: play.size,
      })),
      root_candidates: scoredActions
        .sort((left, right) => right.stats.value - left.stats.value)
        .slice(0, 8)
        .map((candidate) => {
        return {
          action: candidate.action,
          cards: candidate.cards,
          mean_utility: candidate.stats.mean,
          clear_prob: candidate.stats.clearProb,
          confidence: candidate.stats.confidence,
          lower_quantile: candidate.stats.lowerQuantile,
          risk_adjusted_value: candidate.stats.value,
        };
      }),
      chosen: {
        action: best.action,
        cards: best.cards,
        mean_utility: best.stats.mean,
        clear_prob: best.stats.clearProb,
        confidence: best.stats.confidence,
        lower_quantile: best.stats.lowerQuantile,
        risk_adjusted_value: best.stats.value,
      },
      options,
    },
  };
}

function main() {
  const options = parseArgs();
  const state = JSON.parse(readStdin());
  const action = chooseRootAction(state, options);
  process.stdout.write(`${JSON.stringify(action)}\n`);
}

main();

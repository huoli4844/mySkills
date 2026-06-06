#!/usr/bin/env ruby
# MTEF v3 Snapshot -> LaTeX Converter
# Usage: ruby -I/tmp/mathtype/lib mtef_to_latex.rb <eqn_dir> <output_dir>

require "mathtype"
require "fileutils"
require "json"

class MTEFToLaTeX
  # Unicode math symbols that need special LaTeX handling
  MATH_UNICODE = {
    "0x2207" => "\\nabla",
    "0x2202" => "\\partial",
    "0x2211" => "\\sum",
    "0x220F" => "\\prod",
    "0x222B" => "\\int",
    "0x222C" => "\\iint",
    "0x222D" => "\\iiint",
    "0x221A" => "\\sqrt",
    "0x221E" => "\\infty",
    "0x2260" => "\\neq",
    "0x2264" => "\\leq",
    "0x2265" => "\\geq",
    "0x00B1" => "\\pm",
    "0x2213" => "\\mp",
    "0x00D7" => "\\times",
    "0x00F7" => "\\div",
    "0x22C5" => "\\cdot",
    "0x2212" => "-",
    "0x2261" => "\\equiv",
    "0x2248" => "\\approx",
    "0x2192" => "\\rightarrow",
    "0x2190" => "\\leftarrow",
    "0x2191" => "\\uparrow",
    "0x2193" => "\\downarrow",
    "0x21D2" => "\\Rightarrow",
    "0x21D4" => "\\Leftrightarrow",
    "0x2208" => "\\in",
    "0x2209" => "\\notin",
    "0x2229" => "\\cap",
    "0x222A" => "\\cup",
    "0x2282" => "\\subset",
    "0x2283" => "\\supset",
    "0x2286" => "\\subseteq",
    "0x2287" => "\\supseteq",
    "0x2205" => "\\emptyset",
    "0x2220" => "\\angle",
    "0x22A5" => "\\bot",
    "0x2225" => "\\parallel",
    "0x221D" => "\\propto",
    "0x2218" => "\\circ",
    "0x2295" => "\\oplus",
    "0x2297" => "\\otimes",
    "0x2299" => "\\odot",
    "0x22C6" => "\\star",
    "0x210F" => "\\hbar",
    "0x2032" => "'",
    "0x2033" => "''",
    "0x2102" => "\\mathbb{C}",
    "0x211D" => "\\mathbb{R}",
    "0x2115" => "\\mathbb{N}",
    "0x2124" => "\\mathbb{Z}",
    "0x2119" => "\\mathbb{P}",
    "0x211A" => "\\mathbb{Q}",
    "0x2200" => "\\forall",
    "0x2203" => "\\exists",
    "0x2204" => "\\nexists",
    "0x2227" => "\\wedge",
    "0x2228" => "\\vee",
    "0x00AC" => "\\neg",
    "0x22A4" => "\\top",
    "0x221A" => "\\surd",
    "0x03B1" => "\\alpha",
    "0x03B2" => "\\beta",
    "0x03B3" => "\\gamma",
    "0x03B4" => "\\delta",
    "0x03B5" => "\\varepsilon",
    "0x03B6" => "\\zeta",
    "0x03B7" => "\\eta",
    "0x03B8" => "\\theta",
    "0x03B9" => "\\iota",
    "0x03BA" => "\\kappa",
    "0x03BB" => "\\lambda",
    "0x03BC" => "\\mu",
    "0x03BD" => "\\nu",
    "0x03BE" => "\\xi",
    "0x03BF" => "o",
    "0x03C0" => "\\pi",
    "0x03C1" => "\\rho",
    "0x03C3" => "\\sigma",
    "0x03C4" => "\\tau",
    "0x03C5" => "\\upsilon",
    "0x03C6" => "\\varphi",
    "0x03C7" => "\\chi",
    "0x03C8" => "\\psi",
    "0x03C9" => "\\omega",
    "0x0391" => "A",
    "0x0392" => "B",
    "0x0393" => "\\Gamma",
    "0x0394" => "\\Delta",
    "0x0395" => "E",
    "0x0396" => "Z",
    "0x0397" => "H",
    "0x0398" => "\\Theta",
    "0x0399" => "I",
    "0x039A" => "K",
    "0x039B" => "\\Lambda",
    "0x039C" => "M",
    "0x039D" => "N",
    "0x039E" => "\\Xi",
    "0x039F" => "O",
    "0x03A0" => "\\Pi",
    "0x03A1" => "P",
    "0x03A3" => "\\Sigma",
    "0x03A4" => "T",
    "0x03A5" => "\\Upsilon",
    "0x03A6" => "\\Phi",
    "0x03A7" => "X",
    "0x03A8" => "\\Psi",
    "0x03A9" => "\\Omega",
    "0x03D1" => "\\vartheta",
    "0x03D5" => "\\phi",
    "0x03F1" => "\\varrho",
    "0x03C2" => "\\varsigma",
    "0x03D6" => "\\varpi",
    "0x0192" => "f",
    "0x3001" => "\\text{、}",
    "0x3002" => "\\text{。}",
    "0xFF0C" => "\\text{，}",
    "0xFF0E" => "\\text{.}",
    "0xFF1B" => "\\text{；}",
    "0xFF1A" => "\\text{：}",
    "0xFF08" => "\\text{（}",
    "0xFF09" => "\\text{）}",
    "0xFF1F" => "\\text{？}",
    "0xFF01" => "\\text{！}",
    "0x2018" => "\\text{`}",
    "0x2019" => "\\text{'}",
    "0x201C" => "\\text{``}",
    "0x201D" => "\\text{''}",
    "0x2026" => "\\ldots",
    "0x2013" => "\\text{--}",
    "0x2014" => "\\text{---}",
    "0x02DC" => "\\sim",
    "0x2030" => "\\text{\\textperthousand}",
    "0x212B" => "\\mathring{A}",
    "0x00B0" => "^\\circ",
    "0x2033" => "''",
    "0x2035" => "\\backprime",
    "0x221A" => "\\sqrt",
    "0x221B" => "\\sqrt[3]",
    "0x221C" => "\\sqrt[4]",
    "0x222E" => "\\oint",
    "0x2233" => "\\varointclockwise",
    "0x2232" => "\\ointctrclockwise",
    "0x222F" => "\\oiint",
    "0x2230" => "\\oiiint",
    "0x226A" => "\\ll",
    "0x226B" => "\\gg",
    "0x227A" => "\\prec",
    "0x227B" => "\\succ",
    "0x2282" => "\\subset",
    "0x2283" => "\\supset",
    "0x2286" => "\\subseteq",
    "0x2287" => "\\supseteq",
    "0x2291" => "\\sqsubseteq",
    "0x2292" => "\\sqsupseteq",
    "0x22A2" => "\\vdash",
    "0x22A3" => "\\dashv",
    "0x22A6" => "\\vDash",
    "0x22A7" => "\\Vdash",
    "0x22A8" => "\\Vvdash",
    "0x22A9" => "\\VDash",
    "0x22C8" => "\\bowtie",
    "0x22C9" => "\\ltimes",
    "0x22CA" => "\\rtimes",
    "0x22CB" => "\\leftthreetimes",
    "0x22CC" => "\\rightthreetimes",
    "0x22CE" => "\\curlyvee",
    "0x22CF" => "\\curlywedge",
    "0x22D2" => "\\Cap",
    "0x22D3" => "\\Cup",
    "0x22D8" => "\\lll",
    "0x22D9" => "\\ggg",
    "0x22DA" => "\\lesseqgtr",
    "0x22DB" => "\\gtreqless",
    "0x22DE" => "\\curlyeqprec",
    "0x22DF" => "\\curlyeqsucc",
    "0x22E0" => "\\npreceq",
    "0x22E1" => "\\nsucceq",
    "0x22E6" => "\\lnsim",
    "0x22E7" => "\\gnsim",
    "0x22E8" => "\\precnsim",
    "0x22E9" => "\\succnsim",
    "0x22EA" => "\\ntriangleleft",
    "0x22EB" => "\\ntriangleright",
    "0x22EC" => "\\ntrianglelefteq",
    "0x22ED" => "\\ntrianglerighteq",
    "0x2308" => "\\lceil",
    "0x2309" => "\\rceil",
    "0x230A" => "\\lfloor",
    "0x230B" => "\\rfloor",
    "0x2329" => "\\langle",
    "0x232A" => "\\rangle",
    "0x25B3" => "\\triangle",
    "0x25BD" => "\\triangledown",
    "0x25C1" => "\\triangleleft",
    "0x25B7" => "\\triangleright",
    "0x25CB" => "\\circ",
    "0x25CF" => "\\bullet",
    "0x2206" => "\\Delta",
    "0x220F" => "\\prod",
    "0x2210" => "\\coprod",
    "0x2211" => "\\sum",
    "0x2229" => "\\cap",
    "0x222A" => "\\cup",
    "0x222B" => "\\int",
    "0x222C" => "\\iint",
    "0x222D" => "\\iiint",
    "0x222E" => "\\oint",
    "0x2232" => "\\varointclockwise",
    "0x2233" => "\\ointctrclockwise",
    "0x2236" => ":",
    "0x2237" => "::",
    "0x223C" => "\\sim",
    "0x2240" => "\\wr",
    "0x2243" => "\\simeq",
    "0x2245" => "\\cong",
    "0x224D" => "\\asymp",
    "0x2250" => "\\doteq",
    "0x2251" => "\\doteqdot",
    "0x2252" => "\\fallingdotseq",
    "0x2253" => "\\risingdotseq",
    "0x2254" => ":=",
    "0x2255" => "=:",
    "0x2256" => "\\eqcirc",
    "0x2257" => "\\circeq",
    "0x2259" => "\\wedgeq",
    "0x225A" => "\\veeeq",
    "0x225C" => "\\triangleq",
    "0x2260" => "\\neq",
    "0x2261" => "\\equiv",
    "0x2262" => "\\not\\equiv",
    "0x2264" => "\\leq",
    "0x2265" => "\\geq",
    "0x2266" => "\\leqq",
    "0x2267" => "\\geqq",
    "0x2268" => "\\lneqq",
    "0x2269" => "\\gneqq",
    "0x226A" => "\\ll",
    "0x226B" => "\\gg",
    "0x226C" => "\\between",
    "0x226D" => "\\not\\asymp",
    "0x226E" => "\\nless",
    "0x226F" => "\\ngtr",
    "0x2270" => "\\nleq",
    "0x2271" => "\\ngeq",
    "0x2272" => "\\lesssim",
    "0x2273" => "\\gtrsim",
    "0x2276" => "\\lessgtr",
    "0x2277" => "\\gtrless",
    "0x2278" => "\\not\\lessgtr",
    "0x2279" => "\\not\\gtrless",
    "0x227A" => "\\prec",
    "0x227B" => "\\succ",
    "0x227C" => "\\preccurlyeq",
    "0x227D" => "\\succcurlyeq",
    "0x227E" => "\\precsim",
    "0x227F" => "\\succsim",
    "0x2280" => "\\nprec",
    "0x2281" => "\\nsucc",
    "0x2282" => "\\subset",
    "0x2283" => "\\supset",
    "0x2284" => "\\not\\subset",
    "0x2285" => "\\not\\supset",
    "0x2286" => "\\subseteq",
    "0x2287" => "\\supseteq",
    "0x2288" => "\\not\\subseteq",
    "0x2289" => "\\not\\supseteq",
    "0x228A" => "\\subsetneq",
    "0x228B" => "\\supsetneq",
    "0x228E" => "\\uplus",
    "0x228F" => "\\sqsubset",
    "0x2290" => "\\sqsupset",
    "0x2291" => "\\sqsubseteq",
    "0x2292" => "\\sqsupseteq",
    "0x2293" => "\\sqcap",
    "0x2294" => "\\sqcup",
    "0x2295" => "\\oplus",
    "0x2296" => "\\ominus",
    "0x2297" => "\\otimes",
    "0x2298" => "\\oslash",
    "0x2299" => "\\odot",
    "0x229A" => "\\circledcirc",
    "0x229B" => "\\circledast",
    "0x229D" => "\\circleddash",
    "0x229E" => "\\boxplus",
    "0x229F" => "\\boxminus",
    "0x22A0" => "\\boxtimes",
    "0x22A1" => "\\boxdot",
    "0x22A2" => "\\vdash",
    "0x22A3" => "\\dashv",
    "0x22A4" => "\\top",
    "0x22A5" => "\\bot",
    "0x22A6" => "\\vDash",
    "0x22A7" => "\\Vdash",
    "0x22A8" => "\\Vvdash",
    "0x22A9" => "\\Vdash",
    "0x22AA" => "\\Vvdash",
    "0x22AB" => "\\VDash",
    "0x22AC" => "\\not\\vdash",
    "0x22AD" => "\\not\\vDash",
    "0x22AE" => "\\not\\Vdash",
    "0x22AF" => "\\not\\Vvdash",
    "0x22B0" => "\\prurel",
    "0x22B1" => "\\scurel",
    "0x22B2" => "\\vartriangleleft",
    "0x22B3" => "\\vartriangleright",
    "0x22B4" => "\\trianglelefteq",
    "0x22B5" => "\\trianglerighteq",
    "0x22B6" => "\\multimap",
    "0x22B7" => "\\multimapinv",
    "0x22B8" => "\\multimapboth",
    "0x22B9" => "\\multimapdot",
    "0x22BA" => "\\multimapdotinv",
    "0x22BB" => "\\multimapdotboth",
    "0x22BC" => "\\barwedge",
    "0x22BD" => "\\veebar",
    "0x22BE" => "\\measuredangle",
    "0x22BF" => "\\sphericalangle",
    "0x22C0" => "\\bigwedge",
    "0x22C1" => "\\bigvee",
    "0x22C2" => "\\bigcap",
    "0x22C3" => "\\bigcup",
    "0x22C4" => "\\diamond",
    "0x22C5" => "\\cdot",
    "0x22C6" => "\\star",
    "0x22C7" => "\\divideontimes",
    "0x22C8" => "\\bowtie",
    "0x22C9" => "\\ltimes",
    "0x22CA" => "\\rtimes",
    "0x22CB" => "\\leftthreetimes",
    "0x22CC" => "\\rightthreetimes",
    "0x22CE" => "\\curlyvee",
    "0x22CF" => "\\curlywedge",
    "0x22D0" => "\\Subset",
    "0x22D1" => "\\Supset",
    "0x22D2" => "\\Cap",
    "0x22D3" => "\\Cup",
    "0x22D4" => "\\pitchfork",
    "0x22D5" => "\\hash",
    "0x22D6" => "\\lessdot",
    "0x22D7" => "\\gtrdot",
    "0x22D8" => "\\lll",
    "0x22D9" => "\\ggg",
    "0x22DA" => "\\lesseqgtr",
    "0x22DB" => "\\gtreqless",
    "0x22DC" => "\\eqless",
    "0x22DD" => "\\eqgtr",
    "0x22DE" => "\\curlyeqprec",
    "0x22DF" => "\\curlyeqsucc",
    "0x22E0" => "\\npreceq",
    "0x22E1" => "\\nsucceq",
    "0x22E2" => "\\nsqsubseteq",
    "0x22E3" => "\\nsqsupseteq",
    "0x22E4" => "\\sqsubsetneq",
    "0x22E5" => "\\sqsupsetneq",
    "0x22E6" => "\\lnsim",
    "0x22E7" => "\\gnsim",
    "0x22E8" => "\\precnsim",
    "0x22E9" => "\\succnsim",
    "0x22EA" => "\\ntriangleleft",
    "0x22EB" => "\\ntriangleright",
    "0x22EC" => "\\ntrianglelefteq",
    "0x22ED" => "\\ntrianglerighteq",
    "0x22EE" => "\\vdots",
    "0x22EF" => "\\cdots",
    "0x22F0" => "\\iddots",
    "0x22F1" => "\\ddots",
    "0x2300" => "\\varnothing",
    "0x2305" => "\\barwedge",
    "0x2306" => "\\perspcorrespondence",
    "0x2310" => "\\invnot",
    "0x2312" => "\\frown",
    "0x2319" => "\\turnednot",
    "0x2322" => "\\frown",
    "0x2323" => "\\smile",
    "0x2329" => "\\langle",
    "0x232A" => "\\rangle",
    "0x23B0" => "\\left\\{",
    "0x23B1" => "\\right\\}",
    "0x25A1" => "\\square",
    "0x25B3" => "\\triangle",
    "0x25B4" => "\\blacktriangle",
    "0x25B5" => "\\blacktriangleright",
    "0x25B6" => "\\blacktriangleright",
    "0x25B7" => "\\triangleright",
    "0x25B8" => "\\blacktriangleright",
    "0x25B9" => "\\triangleright",
    "0x25BC" => "\\blacktriangledown",
    "0x25BD" => "\\triangledown",
    "0x25BE" => "\\blacktriangledown",
    "0x25BF" => "\\triangledown",
    "0x25C0" => "\\blacktriangleleft",
    "0x25C1" => "\\triangleleft",
    "0x25C2" => "\\blacktriangleleft",
    "0x25C3" => "\\triangleleft",
    "0x25C4" => "\\blacktriangleleft",
    "0x25C5" => "\\triangleleft",
    "0x25CA" => "\\lozenge",
    "0x25CB" => "\\bigcirc",
    "0x25CC" => "\\dottedcircle",
    "0x25CF" => "\\bullet",
    "0x25D0" => "\\LEFTcircle",
    "0x25D1" => "\\RIGHTcircle",
    "0x25D2" => "\\circlebottomhalfblack",
    "0x25D3" => "\\circletophalfblack",
    "0x25D4" => "\\circlelefthalfblack",
    "0x25D5" => "\\circlerighthalfblack",
    "0x25D6" => "\\blacktriangleright",
    "0x25D7" => "\\blacktriangleright",
    "0x25D8" => "\\inversebullet",
    "0x25D9" => "\\inversewhitecircle",
    "0x25DA" => "\\invwhiteupperhalfcircle",
    "0x25DB" => "\\invwhiteupperhalfcircle",
    "0x25DC" => "\\ularc",
    "0x25DD" => "\\urarc",
    "0x25DE" => "\\lrarc",
    "0x25DF" => "\\llarc",
    "0x25E0" => "\\frown",
    "0x25E1" => "\\smile",
    "0x25E2" => "\\varhexagon",
    "0x25E3" => "\\varhexagon",
    "0x25E4" => "\\varhexagon",
    "0x25E5" => "\\varhexagon",
    "0x25E6" => "\\circ",
    "0x25EF" => "\\bigcirc",
    "0x2660" => "\\spadesuit",
    "0x2661" => "\\heartsuit",
    "0x2662" => "\\diamondsuit",
    "0x2663" => "\\clubsuit",
    "0x266D" => "\\flat",
    "0x266E" => "\\natural",
    "0x266F" => "\\sharp",
    "0x27E8" => "\\langle",
    "0x27E9" => "\\rangle",
    "0x27EA" => "\\llangle",
    "0x27EB" => "\\rrangle",
    "0x27F5" => "\\longleftarrow",
    "0x27F6" => "\\longrightarrow",
    "0x27F7" => "\\longleftrightarrow",
    "0x27F8" => "\\Longleftarrow",
    "0x27F9" => "\\Longrightarrow",
    "0x27FA" => "\\Longleftrightarrow",
    "0x27FB" => "\\longmapsfrom",
    "0x27FC" => "\\longmapsto",
    "0x27FD" => "\\Longmapsfrom",
    "0x27FE" => "\\Longmapsto",
    "0x27FF" => "\\longrightsquigarrow",
  }

  EMBELL_LATEX = {
    "emb1DOT" => "\\dot",
    "emb2DOT" => "\\ddot",
    "emb3DOT" => "\\dddot",
    "emb4DOT" => "\\ddddot",
    "emb1PRIME" => nil,  # handled as postfix '
    "emb2PRIME" => nil,  # handled as postfix ''
    "emb3PRIME" => nil,
    "embBPRIME" => nil,
    "embTILDE" => "\\tilde",
    "embHAT" => "\\hat",
    "embNOT" => "\\not",
    "embRARROW" => "\\vec",
    "embLARROW" => "\\overleftarrow",
    "embBARROW" => "\\overleftrightarrow",
    "embR1ARROW" => "\\vec",
    "embL1ARROW" => "\\overleftarrow",
    "embMBAR" => "\\bar",
    "embOBAR" => "\\bar",
    "embFROWN" => "\\wideparen",
    "embSMILE" => "\\smile",
    "embX_BARS" => nil,
    "embUP_BAR" => nil,
    "embDOWN_BAR" => nil,
    "embU_1DOT" => "\\dot",
    "embU_2DOT" => "\\ddot",
    "embU_3DOT" => "\\dddot",
    "embU_4DOT" => "\\ddddot",
    "embU_BAR" => "\\bar",
    "embU_TILDE" => "\\tilde",
    "embU_FROWN" => nil,
    "embU_SMILE" => nil,
    "embU_RARROW" => "\\underrightarrow",
    "embU_LARROW" => "\\underleftarrow",
    "embU_BARROW" => "\\underleftrightarrow",
    "embU_R1ARROW" => "\\underrightarrow",
    "embU_L1ARROW" => "\\underleftarrow",
  }

  FENCE_CHARS = {
    "0x0028" => "(",    # (
    "0x0029" => ")",    # )
    "0x005B" => "[",    # [
    "0x005D" => "]",    # ]
    "0x007B" => "\\{", # {
    "0x007D" => "\\}", # }
    "0x007C" => "|",    # |
    "0x2016" => "\\|",  # ||
    "0x230A" => "\\lfloor",
    "0x230B" => "\\rfloor",
    "0x2308" => "\\lceil",
    "0x2309" => "\\rceil",
    "0x27E8" => "\\langle",
    "0x27E9" => "\\rangle",
    "0x2329" => "\\langle",
    "0x232A" => "\\rangle",
  }

  def initialize
  end

  def convert(snapshot)
    equation = snapshot[:equation]
    return "" unless equation
    process_array(equation).strip
  end

  def process(obj)
    case obj
    when Hash
      process_hash(obj)
    when Array
      process_array(obj)
    else
      obj.to_s
    end
  end

  def process_array(arr)
    # Special handling for LINE content: tmSUB/tmSUP/tmSUBSUP base is the preceding element
    result = []
    arr.each do |item|
      processed = process(item)
      if processed.is_a?(Hash) && processed[:type] == :script_template
        # Apply script to previous element
        if result.empty?
          # No base available, just render the script content
          result << processed[:latex]
        else
          base = result.pop
          if processed[:sub] && !processed[:sub].empty? && processed[:sup] && !processed[:sup].empty?
            result << "#{base}_{#{processed[:sub]}}^{#{processed[:sup]}}"
          elsif processed[:sub] && !processed[:sub].empty?
            result << "#{base}_{#{processed[:sub]}}"
          elsif processed[:sup] && !processed[:sup].empty?
            result << "#{base}^{#{processed[:sup]}}"
          else
            result << base  # no script content, just restore base
          end
        end
      else
        # Fix LaTeX command粘连: \omega t -> \omega t
        if !result.empty? && processed.is_a?(String) && !processed.empty?
          last = result.last
          if last.is_a?(String) && last.match?(/\\[a-zA-Z]+$/) && processed.match?(/^[a-zA-Z]/)
            result[-1] = last + " "
          end
        end
        result << processed
      end
    end
    result.join("")
  end

  def process_hash(hash)
    type = hash[:record_type]
    case type
    when 0  # END
      ""
    when 1  # LINE / slot
      payload = hash[:payload] || {}
      # If options has xfNULL (0x01), skip
      return "" if (payload[:options].to_i & 0x01) != 0
      list = payload[:object_list] || []
      process_array(list)
    when 2  # CHAR
      char_to_latex(hash[:payload])
    when 3  # TMPL
      tmpl_to_latex(hash[:payload])
    when 4  # PILE
      pile_to_latex(hash[:payload])
    when 5  # MATRIX
      matrix_to_latex(hash[:payload])
    when 6  # EMBELL
      ""  # handled within CHAR
    when 7  # RULER
      ""
    when 8  # FONT
      ""
    when 9  # SIZE
      ""
    when 10 # FULL
      ""
    when 11 # SUB
      ""
    when 12 # SUB2
      ""
    when 13 # SYM
      sym_to_latex(hash[:payload])
    when 14 # SUBSYM
      ""
    when 15, 16, 17, 18, 19, 20, 21, 22, 23
      # MTEF v5 definition records: font_def, eqn_prefs, encoding_def, etc.
      ""
    else
      ""
    end
  end

  def char_to_latex(payload)
    return "" unless payload
    code = payload[:mt_code_value]
    return "" unless code

    # Convert hex string to Unicode character
    char = unicode_from_hex(code)
    latex_char = MATH_UNICODE[code] || escape_latex(char)

    # Handle embellishments
    embell_list = payload[:embellishment_list] || []
    embellishments = embell_list.select { |e| e.is_a?(Hash) && e[:record_type] == 6 }
    embellishments.each do |embell|
      emb_name = embell.dig(:payload, :embell)
      next unless emb_name
      cmd = EMBELL_LATEX[emb_name]
      if cmd
        latex_char = "#{cmd}{#{latex_char}}"
      elsif emb_name.include?("PRIME")
        count = case emb_name
                when "emb1PRIME" then "'"
                when "emb2PRIME" then "''"
                when "emb3PRIME" then "'''"
                when "embBPRIME" then "\\backprime"
                else "'"
                end
        latex_char = "#{latex_char}#{count}"
      end
    end

    latex_char
  end

  def unicode_from_hex(hex_str)
    return "" if hex_str.nil? || hex_str.empty?
    [hex_str.sub(/^0x/, "").hex].pack("U")
  rescue
    ""
  end

  def escape_latex(str)
    return "" if str.nil?
    str.gsub(/([#$%&_{}~^\\])/) do |m|
      case m
      when "\\" then "\\textbackslash{}"
      when "~" then "\\textasciitilde{}"
      when "^" then "\\textasciicircum{}"
      else "\\#{m}"
      end
    end
  end

  def tmpl_to_latex(payload)
    return "" unless payload
    selector = payload[:selector]
    subobjects = payload[:subobject_list] || []

    case selector
    when "tmSUB"
      # subobject_list: [SUB, LINE(sub), LINE(empty/sup), END]
      # Base is the preceding element in the parent LINE
      sub = process(subobjects[1])
      sup = process(subobjects[2])
      if sub.empty? && sup.empty?
        ""
      else
        { type: :script_template, sub: sub, sup: sup }
      end
    when "tmSUP"
      sub = process(subobjects[1])
      sup = process(subobjects[2])
      if sub.empty? && sup.empty?
        ""
      else
        { type: :script_template, sub: sub, sup: sup }
      end
    when "tmSUBSUP"
      sub = process(subobjects[1])
      sup = process(subobjects[2])
      if sub.empty? && sup.empty?
        ""
      else
        { type: :script_template, sub: sub, sup: sup }
      end
    when "tmFRACT"
      # subobject_list: [LINE(num), LINE(denom), END]
      num = process(subobjects[0])
      denom = process(subobjects[1])
      "\\frac{#{num}}{#{denom}}"
    when "tmPAREN", "tmBRACK", "tmBRACE", "tmANGLE", "tmBAR", "tmDBAR", "tmFLOOR", "tmCEILING", "tmOBRACK"
      fence_to_latex(selector, subobjects)
    when "tmROOT"
      # subobject_list: [LINE(index/nth), LINE(radicand), END]
      # tvROOT_SQ: no index; tvROOT_NTH: has index
      variation = payload[:variation] || []
      if variation.include?("tvROOT_NTH")
        index = process(subobjects[0])
        radicand = process(subobjects[1])
        "\\sqrt[#{index}]{#{radicand}}"
      else
        radicand = process(subobjects[0])
        "\\sqrt{#{radicand}}"
      end
    when "tmINTEG"
      integral_to_latex(payload, subobjects)
    when "tmSUM", "tmPROD", "tmCOPROD", "tmUNION", "tmINTER", "tmINTOP", "tmSUMOP"
      bigop_to_latex(selector, payload, subobjects)
    when "tmVEC"
      # subobject_list: [LINE(base), END]
      base = process(subobjects[0])
      variation = payload[:variation] || []
      if variation.include?("tvVE_UNDER")
        "\\underrightarrow{#{base}}"
      else
        "\\vec{#{base}}"
      end
    when "tmHAT"
      base = process(subobjects[0])
      "\\hat{#{base}}"
    when "tmTILDE"
      base = process(subobjects[0])
      "\\tilde{#{base}}"
    when "tmUBAR"
      base = process(subobjects[0])
      "\\underline{#{base}}"
    when "tmOBAR"
      base = process(subobjects[0])
      "\\overline{#{base}}"
    when "tmARROW"
      # Arrow with optional top/bottom slots
      variation = payload[:variation] || []
      top = variation.include?("tvAR_TOP") ? process(subobjects[0]) : ""
      bottom = variation.include?("tvAR_BOTTOM") ? process(subobjects[1]) : ""
      base = process(subobjects.find { |s| s.is_a?(Hash) && s[:record_type] == 1 })
      arrow_cmd = "\\xrightarrow"
      if top.empty? && bottom.empty?
        "#{arrow_cmd}{#{base}}"
      elsif bottom.empty?
        "#{arrow_cmd}[#{base}]{#{top}}"
      else
        "#{arrow_cmd}[#{bottom}]{#{top}}"
      end
    when "tmLDIV"
      # Long division
      upper = process(subobjects[0])
      lower = process(subobjects[1])
      "#{upper} \\overline{)#{lower}}"
    when "tmBOX"
      base = process(subobjects[0])
      "\\boxed{#{base}}"
    when "tmSTRIKE"
      base = process(subobjects[0])
      variation = payload[:variation] || []
      if variation.include?("tvST_HORIZ")
        "\\sout{#{base}}"
      else
        "\\cancel{#{base}}"
      end
    when "tmHBRACE", "tmHBRACK"
      variation = payload[:variation] || []
      is_top = variation.include?("tvHB_TOP")
      base = process(subobjects[0])
      if is_top
        "\\overbrace{#{base}}"
      else
        "\\underbrace{#{base}}"
      end
    when "tmDIRAC"
      # Bra-ket notation
      variation = payload[:variation] || []
      left = variation.include?("tvDI_LEFT") ? process(subobjects[0]) : ""
      right = variation.include?("tvDI_RIGHT") ? process(subobjects[1]) : ""
      "\\langle #{left} | #{right} \\rangle"
    when "tmLIM"
      # Limit
      variation = payload[:variation] || []
      lower = variation.include?("tvBO_LOWER") ? process(subobjects[0]) : ""
      upper = variation.include?("tvBO_UPPER") ? process(subobjects[1]) : ""
      base = process(subobjects.find { |s| s.is_a?(Hash) && s[:record_type] == 1 })
      if upper.empty?
        "\\lim_{#{lower}} #{base}"
      else
        "\\lim_{#{lower}}^{#{upper}} #{base}"
      end
    when "tmSCRIPT"
      # Generic script - determine from subobjects
      if subobjects.length >= 4
        base = process(subobjects[1])
        sub = process(subobjects[2])
        sup = process(subobjects[3])
        if sub.empty?
          "#{base}^{#{sup}}"
        elsif sup.empty?
          "#{base}_{#{sub}}"
        else
          "#{base}_{#{sub}}^{#{sup}}"
        end
      else
        process_array(subobjects)
      end
    else
      # Unknown template - just process children
      process_array(subobjects)
    end
  end

  def fence_to_latex(selector, subobjects)
    # subobjects: [LINE(content), CHAR(left_fence)?, CHAR(right_fence)?, END]
    content_parts = []
    left_fence = nil
    right_fence = nil

    subobjects.each do |obj|
      next unless obj.is_a?(Hash)
      case obj[:record_type]
      when 1
        content_parts << process(obj)
      when 2
        code = obj.dig(:payload, :mt_code_value)
        if left_fence.nil?
          left_fence = FENCE_CHARS[code] || unicode_from_hex(code)
        else
          right_fence = FENCE_CHARS[code] || unicode_from_hex(code)
        end
      end
    end

    content = content_parts.join("")

    # Default fences based on selector
    if left_fence.nil? || right_fence.nil?
      case selector
      when "tmPAREN" then left_fence = "(" ; right_fence = ")"
      when "tmBRACK" then left_fence = "[" ; right_fence = "]"
      when "tmBRACE" then left_fence = "\\{" ; right_fence = "\\}"
      when "tmANGLE" then left_fence = "\\langle" ; right_fence = "\\rangle"
      when "tmBAR" then left_fence = "|" ; right_fence = "|"
      when "tmDBAR" then left_fence = "\\|" ; right_fence = "\\|"
      when "tmFLOOR" then left_fence = "\\lfloor" ; right_fence = "\\rfloor"
      when "tmCEILING" then left_fence = "\\lceil" ; right_fence = "\\rceil"
      end
    end

    if left_fence && right_fence
      "\\left#{left_fence} #{content} \\right#{right_fence}"
    else
      content
    end
  end

  def integral_to_latex(payload, subobjects)
    variation = payload[:variation] || []
    int_count = 1
    int_count = 2 if variation.include?("tvINT_2")
    int_count = 3 if variation.include?("tvINT_3")

    int_symbol = "\\int"
    int_symbol = "\\iint" if int_count == 2
    int_symbol = "\\iiint" if int_count == 3

    has_lower = variation.include?("tvBO_LOWER")
    has_upper = variation.include?("tvBO_UPPER")
    is_sum_style = variation.include?("tvBO_SUM")

    # Find the integral sign character if present, otherwise use slots
    integral_char = nil
    content_idx = 0

    subobjects.each_with_index do |obj, i|
      if obj.is_a?(Hash) && obj[:record_type] == 2
        integral_char = process(obj)
        content_idx = i + 1
        break
      end
    end

    # Collect limit slots and content
    slots = subobjects.select { |s| s.is_a?(Hash) && s[:record_type] == 1 }
    lower = has_lower && slots[0] ? process(slots[0]) : ""
    upper = has_upper && slots[1] ? process(slots[1]) : ""
    content = process(slots.last) if slots.last
    content = "" if content.nil?

    if has_lower && has_upper
      "#{int_symbol}_{#{lower}}^{#{upper}} #{content}"
    elsif has_lower
      "#{int_symbol}_{#{lower}} #{content}"
    else
      "#{int_symbol} #{content}"
    end
  end

  def bigop_to_latex(selector, payload, subobjects)
    variation = payload[:variation] || []
    has_lower = variation.include?("tvBO_LOWER")
    has_upper = variation.include?("tvBO_UPPER")
    is_sum_style = variation.include?("tvBO_SUM")

    op_symbol = case selector
                when "tmSUM" then "\\sum"
                when "tmPROD" then "\\prod"
                when "tmCOPROD" then "\\coprod"
                when "tmUNION" then "\\bigcup"
                when "tmINTER" then "\\bigcap"
                when "tmINTOP" then "\\intop"
                when "tmSUMOP" then "\\sum"
                else "\\sum"
                end

    # Collect limit slots and content
    slots = subobjects.select { |s| s.is_a?(Hash) && s[:record_type] == 1 }
    lower = has_lower && slots[0] ? process(slots[0]) : ""
    upper = has_upper && slots[1] ? process(slots[1]) : ""
    content = process(slots.last) if slots.last
    content = "" if content.nil?

    if has_lower && has_upper
      "#{op_symbol}_{#{lower}}^{#{upper}} #{content}"
    elsif has_lower
      "#{op_symbol}_{#{lower}} #{content}"
    else
      "#{op_symbol} #{content}"
    end
  end

  def pile_to_latex(payload)
    return "" unless payload
    lines = payload[:object_list] || []
    # Filter out END records and empty lines
    valid_lines = lines.select { |l| l.is_a?(Hash) && l[:record_type] == 1 }
    latex_lines = valid_lines.map { |l| process(l) }
    "\\begin{array}{c} #{latex_lines.join(" \\\\\\n ")} \\end{array}"
  end

  def matrix_to_latex(payload)
    return "" unless payload
    lines = payload[:object_list] || []
    valid_lines = lines.select { |l| l.is_a?(Hash) && l[:record_type] == 1 }
    latex_lines = valid_lines.map do |line|
      cells = line.dig(:payload, :object_list) || []
      valid_cells = cells.select { |c| c.is_a?(Hash) && c[:record_type] == 1 }
      valid_cells.map { |c| process(c) }.join(" & ")
    end
    "\\begin{matrix} #{latex_lines.join(" \\\\\\n ")} \\end{matrix}"
  end

  def sym_to_latex(payload)
    return "" unless payload
    # SYM record contains symbol information
    char = char_to_latex(payload)
    char
  end
end

# Main execution
if __FILE__ == $0
  eqn_dir = ARGV[0] || "/tmp/eqn_native"
  output_dir = ARGV[1] || "/tmp/eqn_output"
  FileUtils.mkdir_p(output_dir)

  converter = MTEFToLaTeX.new
  results = []
  errors = []

  Dir.glob(File.join(eqn_dir, "eqn_*.bin")).sort.each do |f|
    begin
      data = File.binread(f)
      if data.bytesize < 29
        errors << { name: File.basename(f, ".bin"), error: "File too small" }
        next
      end

      version = data[28].ord
      mtef_data = data[28..-1]

      snapshot = case version
                 when 3
                   Mathtype3::Equation.read(mtef_data).snapshot
                 when 5
                   Mathtype5::Equation.read(mtef_data).snapshot
                 else
                   raise "Unsupported MTEF version: #{version}"
                 end

      latex = converter.convert(snapshot)

      basename = File.basename(f, ".bin")
      out_path = File.join(output_dir, "#{basename}.tex")
      File.write(out_path, "$#{latex}$")

      results << { name: basename, latex: latex, version: version }
    rescue => e
      errors << { name: File.basename(f, ".bin"), error: e.message }
    end
  end

  # Write summary JSON
  summary = {
    total: results.length + errors.length,
    success: results.length,
    errors: errors.length,
    formulas: results,
    error_details: errors
  }
  File.write(File.join(output_dir, "summary.json"), JSON.pretty_generate(summary))

  puts "Processed #{results.length} formulas, #{errors.length} errors"
  puts "Output directory: #{output_dir}"

  # Print first 30 formulas for verification
  puts "\n--- First 30 formulas ---"
  results.first(30).each do |r|
    puts "#{r[:name]}: #{r[:latex]}"
  end
end

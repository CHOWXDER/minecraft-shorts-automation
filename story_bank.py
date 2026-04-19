"""
story_bank.py — Proven viral hooks + full stories.
Used as fallback when Reddit produces nothing with score >= 7.
Rotates through all 15 so every video is different.
"""

import json
import random
from pathlib import Path

_STATE_FILE = Path("temp/story_state.json")

STORIES = [
    {
        "title": "AITA for leaving my girlfriend at the airport?",
        "text": (
            "We were flying to Mexico for her birthday trip. She was two hours late to the airport, "
            "missed check-in, and just expected me to miss the flight with her and rebook. I'd been "
            "planning this for four months. I got on the plane. She blew up my phone the entire flight. "
            "Now her whole family is calling me heartless. But she knew the check-in time. I reminded "
            "her three times that morning. Am I really the bad guy for not throwing away a non-refundable "
            "ticket because she couldn't leave on time?"
        ),
    },
    {
        "title": "I found out my best friend has been lying to me for years",
        "text": (
            "We've been best friends since middle school. I just found out he's been telling people "
            "I cheated on my ex when we dated, which is completely false. I only found out because "
            "someone screenshot it and sent it to me. He's been doing this for three years. Three years "
            "of people looking at me weird and me having no idea why. When I confronted him he said "
            "it was just a joke that got out of hand. A joke. Three years of my reputation destroyed "
            "and he calls it a joke."
        ),
    },
    {
        "title": "My parents kicked me out for something I did at 16",
        "text": (
            "I'm 22 now. When I was 16 I snuck out to a party. Normal teenager stuff. My parents found "
            "out, screamed at me for an hour, and told me to leave their house. I had nowhere to go so "
            "I stayed with my aunt for two weeks. They eventually let me come back but things were never "
            "the same. Fast forward to now — they want me to move back in to help with bills. I said no. "
            "They're calling me ungrateful. But they literally kicked out their 16 year old kid. Why "
            "would I ever trust them again?"
        ),
    },
    {
        "title": "I got my coworker fired and I don't feel bad",
        "text": (
            "She had been stealing my lunch for two months. I know it sounds petty but I meal prep on "
            "Sundays, I have a strict diet, and she was eating my food every single week. I told my "
            "manager. Manager said she'd handle it. Nothing changed. So I put laxatives in my food — "
            "totally legal, just ExLax chocolate mixed into a brownie. She ate it, spent the afternoon "
            "in the bathroom, and HR somehow found out it was her food. They fired her for theft. "
            "Now the office is divided. Half think I'm a genius, half think I'm evil."
        ),
    },
    {
        "title": "I faked being sick to skip my best friend's wedding",
        "text": (
            "She asked me to be her maid of honor. Then two months before the wedding she replaced me "
            "with her new work friend and demoted me to just a bridesmaid. No explanation. I smiled and "
            "said okay. On the wedding day I texted her saying I had food poisoning and couldn't make it. "
            "I was sitting at home watching Netflix. She hasn't spoken to me since and apparently cried "
            "during the reception. Her mom called me disgusting. But she humiliated me first. I just "
            "chose myself for once."
        ),
    },
    {
        "title": "I told my sister her boyfriend is cheating — she chose him",
        "text": (
            "I saw him on a dating app. Profile was active, photos were recent, bio said single. "
            "I screenshotted everything and sent it to my sister. She confronted him. He said I was "
            "jealous and made it up. She believed him. Blocked me. Told our parents I was trying to "
            "ruin her relationship out of jealousy. My parents are now asking me to apologize to him "
            "to keep the family peace. I'm supposed to apologize to the man who's cheating on my sister "
            "while she watches. I'd rather never speak to any of them again."
        ),
    },
    {
        "title": "I quit my job on the spot in front of everyone",
        "text": (
            "My manager called me out in a team meeting for a mistake that was actually his. He had "
            "the emails to prove it was his call, but he stood there and blamed me in front of fifteen "
            "people. I pulled up the email chain on my laptop, turned the screen toward the room, "
            "and read it out loud. Then I closed my laptop, picked up my bag, and said I quit. "
            "Everyone went silent. He tried to say we should talk in private. I said there was nothing "
            "left to talk about and walked out. Best feeling of my entire life."
        ),
    },
    {
        "title": "My roommate told everyone my secrets after I asked her to leave",
        "text": (
            "We lived together for a year. I gave her two months notice to find somewhere else because "
            "I needed the space for a family member moving in. She was furious. Within a week she told "
            "our entire friend group things I'd told her in private — my mental health struggles, an "
            "old relationship, money problems. All of it. Just weaponized every vulnerable thing I'd "
            "ever shared with her. I haven't left my apartment in days. These were people I trusted. "
            "I don't even know who I can talk to anymore."
        ),
    },
    {
        "title": "I accidentally ruined my brother's proposal",
        "text": (
            "He told me he was proposing at dinner on Saturday. He did not tell me he'd already hidden "
            "the ring in a gift box he left on the kitchen counter. I thought it was a gift for me — "
            "it was my birthday week. I opened it in front of his girlfriend. She saw the ring. He "
            "walked in right at that moment. He proposed anyway, on the spot, in the kitchen, completely "
            "unprepared. She said yes but he didn't speak to me for a week. He says I ruined the moment "
            "he'd been planning for six months. I genuinely thought it was my present."
        ),
    },
    {
        "title": "I stopped paying my girlfriend's rent and she called the cops",
        "text": (
            "For two years I covered her rent while she figured out her career. Six thousand dollars. "
            "When I said I needed to stop because I was struggling financially, she told me I was "
            "abandoning her. I gave her three months notice. She called the police and told them I "
            "was financially abusing her by suddenly withdrawing support. The officer looked confused. "
            "Nothing happened legally but now she's posting about it online. I have screenshots of "
            "every Venmo transfer. Two years of supporting someone and this is what I get."
        ),
    },
    {
        "title": "I told my mom I don't love her anymore",
        "text": (
            "She missed my graduation, my first apartment, my surgery. Every major moment I called her "
            "and she had a reason she couldn't be there. Last week she showed up to my cousin's birthday "
            "party — a party — after skipping my hospital stay. I pulled her aside and told her quietly "
            "that I don't think I love her anymore. Not as a weapon. Just as the truth. She started "
            "crying and now the whole family thinks I'm a monster. But I've been grieving her for years "
            "while she was still alive. I'm just done pretending."
        ),
    },
    {
        "title": "My best friend slept with my ex one week after we broke up",
        "text": (
            "We dated for two years. The breakup was brutal — I was a mess for weeks. My best friend "
            "was there every day, listening, telling me I deserved better. One week after we broke up "
            "I found out they were already together. They'd apparently been texting the whole time we "
            "were dating. He wasn't comforting me — he was waiting. She says they fell for each other "
            "and couldn't help it. He says feelings aren't something you can control. I lost both of "
            "them in the same moment and neither of them thinks they did anything wrong."
        ),
    },
    {
        "title": "I ghosted my entire friend group and I'm not going back",
        "text": (
            "For two years I was the one who organized everything. Every birthday, every dinner, every "
            "group chat message. One month I stopped. Just to see. Not a single person reached out. "
            "Not one. Two years of being the glue and the moment I stopped, silence. I moved to a new "
            "city three months ago. Nobody noticed. Someone posted a group photo from a hangout last "
            "week — they replaced me with someone new and didn't miss a beat. I think I was never "
            "actually their friend. I was just useful."
        ),
    },
    {
        "title": "I reported my landlord and now my neighbors hate me",
        "text": (
            "He hadn't fixed our heating for four months. January in the midwest with no heat. I "
            "reported him to the city. Inspectors came, found twelve violations across the whole "
            "building, and he got fined heavily. Now he's raising everyone's rent to cover it and "
            "my neighbors are furious at me. They're leaving notes on my door. Someone keyed my car. "
            "I had no idea reporting one broken heater would affect the whole building. But also — "
            "he knew about all those violations and chose to do nothing. I'm not the villain here."
        ),
    },
    {
        "title": "I told my boss exactly what I think of him in my exit interview",
        "text": (
            "I had nothing to lose. New job lined up, last day was Friday. HR sat me down for the "
            "exit interview and asked what could be improved. I told them everything. How he takes "
            "credit for our work in front of clients. How he talks down to women on the team. How "
            "he once made someone cry in a performance review and then joked about it. I had dates, "
            "names, incidents. HR looked genuinely shocked. My former manager called me that evening "
            "furious. Apparently HR is now investigating. I slept like a baby."
        ),
    },
    {
        "title": "I uninvited my parents from my wedding and don't regret it",
        "text": (
            "They told me my fiancé wasn't good enough for our family two weeks before the wedding. "
            "Said it at dinner, in front of him. He just sat there. I looked at my mom and said "
            "you're no longer invited. She laughed like I was joking. I wasn't. They showed up to "
            "the venue anyway. Security turned them away. My siblings are furious. My aunt called me "
            "a monster. My husband cried when I told him why I did it. That made it worth everything."
        ),
    },
    {
        "title": "I recorded my coworker stealing and sent it to everyone",
        "text": (
            "She'd been taking credit for my reports for six months. My manager kept praising her "
            "in meetings while I sat there building everything she presented. So I set up my laptop "
            "camera and recorded her downloading my files and putting her name on them. I didn't go "
            "to HR. I forwarded the video to the entire team including the director. She was walked "
            "out that afternoon. People keep asking if I feel bad. I don't. Not even a little."
        ),
    },
    {
        "title": "My husband forgot our anniversary for the third year in a row",
        "text": (
            "I didn't remind him. I didn't hint. I wanted to see if he'd remember on his own. He "
            "didn't. He came home and asked what was for dinner like it was any other Tuesday. I'd "
            "spent the week wondering if I was being unfair. I wasn't. Ten years of marriage and he "
            "can't remember one day. I told him calmly that I'd been thinking about this for a while "
            "and I think we need to talk about whether we still want the same things. He finally "
            "looked up from his phone."
        ),
    },
    {
        "title": "I cut off my brother after what he did at our dad's funeral",
        "text": (
            "Dad died in March. At the reception my brother stood up and gave a speech about how "
            "dad always loved him more and how the rest of us were jealous. At a funeral. In front "
            "of sixty people. My mom started crying. I walked over, took the microphone, and said "
            "this isn't the time or the place and sat him down. He hasn't spoken to me since and "
            "honestly that's fine. Grief doesn't give you permission to humiliate your family."
        ),
    },
    {
        "title": "I caught my boyfriend of four years on a dating app",
        "text": (
            "His phone buzzed while he was in the shower. I wasn't snooping — it was face up on "
            "the counter and the notification showed a match notification from Hinge. I didn't "
            "confront him right away. I made a fake profile, matched with him, and had a full "
            "conversation where he told my fake profile he was single and looking for something "
            "serious. I screenshotted everything. Then I sent it to him from my real number. "
            "He called immediately. I didn't pick up."
        ),
    },
    {
        "title": "I told my sister the truth about her husband and she chose him",
        "text": (
            "For two years I watched him talk down to her in public. Little comments. Corrections. "
            "Sighs when she spoke. I finally sat her down and told her everything I'd observed. "
            "She went home and told him. He told her I was jealous of their relationship. She "
            "called me the next day and said she thinks I need to apologize. I said I'd rather "
            "never see either of them again. She said then don't come to Christmas. I said okay."
        ),
    },
    {
        "title": "I refused to give my inheritance to my siblings and they hate me",
        "text": (
            "My grandmother left everything specifically to me. Not split equally — just me. My "
            "siblings are convinced I manipulated her. I didn't. She and I were close for thirty "
            "years. I visited every week. They visited at Christmas. When the will was read my "
            "brother actually stood up and said this can't be right. I didn't argue. I didn't "
            "explain. I just left. They've been sending emails ever since. I've read none of them."
        ),
    },
    {
        "title": "I exposed my friend group's group chat to the person they were talking about",
        "text": (
            "They'd been mocking her for months. Her clothes, her boyfriend, her job. I was in "
            "the chat but never participated. One day they went too far — someone posted a photo "
            "of her from a party and everyone piled on. I screenshotted the whole thread and "
            "sent it to her anonymously. Then I left the group. She confronted them the next day. "
            "Three of them know it was me. They're calling me a traitor. I'd do it again."
        ),
    },
    {
        "title": "I walked out of my own baby shower",
        "text": (
            "My mother-in-law planned it without asking me. Invited people I don't know. Chose a "
            "theme I hate. Didn't invite my best friend because she quote doesn't fit in with the "
            "family. I arrived, looked around, and fifteen minutes later I told my husband I was "
            "leaving. He asked me to stay for appearances. I said no and drove to my best friend's "
            "house. We ordered food and watched movies. It was the best baby shower I could have "
            "asked for. My mother-in-law hasn't spoken to me since."
        ),
    },
    {
        "title": "I told my dad I don't want him at my graduation",
        "text": (
            "He missed every important thing. School plays. Sports. My mom's surgery. He always "
            "had a reason. When I got into grad school I called to tell him and he was too busy "
            "to talk. So when graduation came I sent him a card that said I love you but I need "
            "this day to be about people who showed up. He called crying. Said I was punishing him "
            "for working hard. I said no, I'm protecting myself from being disappointed again. "
            "He didn't come. It was peaceful."
        ),
    },
    {
        "title": "I returned my engagement ring and left the country",
        "text": (
            "He proposed in front of his entire family before asking me privately. I said yes "
            "because fifty people were watching. Three days later I gave the ring back and "
            "told him I needed him to actually ask me properly when it was just the two of us. "
            "He told his family I rejected him. They bombarded me with messages. So I booked a "
            "flight to Portugal, turned off my phone, and spent two weeks alone. When I came back "
            "he had moved his things out. I considered that my real answer."
        ),
    },
    {
        "title": "I told my mom her new husband makes me uncomfortable and she chose him",
        "text": (
            "He comments on what I eat. How I dress. How much I weigh. Always framed as concern. "
            "I told my mom six months ago that I wasn't comfortable being around him. She said I "
            "was being dramatic and that he's just old fashioned. Last month she told me he'd be "
            "moving into the house I grew up in. I told her I wouldn't be visiting anymore. She "
            "said that's your choice. It is. And I'm at peace with it."
        ),
    },
    {
        "title": "I filed a noise complaint against my neighbor and things escalated",
        "text": (
            "Music every night until two AM. I knocked on the door three times over two months. "
            "Polite every time. Nothing changed. So I called the city and filed a formal complaint. "
            "They got a fine. Now they park in front of my driveway, leave garbage near my door, "
            "and stare at me when I leave for work. I've documented everything. Filed two more "
            "complaints. My other neighbors think I started it. I have thirty days of audio "
            "recordings that say otherwise."
        ),
    },
    {
        "title": "I didn't tell my family I got promoted and I'm glad",
        "text": (
            "Last time I shared good news my brother immediately talked about his own job. My mom "
            "asked if the money would help me pay off my mistakes. My dad said don't let it go to "
            "your head. So when I got promoted to director I told my friends and my therapist. "
            "Not my family. Three months later my cousin mentioned it at a holiday dinner — she'd "
            "seen it on LinkedIn. The table went silent. My mom said why didn't you tell us. "
            "I said I didn't think you'd be interested. Nobody argued."
        ),
    },
]

def _load_used() -> list[int]:
    try:
        return json.loads(_STATE_FILE.read_text())
    except Exception:
        return []

def _save_used(used: list[int]) -> None:
    _STATE_FILE.parent.mkdir(exist_ok=True)
    _STATE_FILE.write_text(json.dumps(used))


def get_story() -> dict:
    """Return the next story, cycling through all 15 before repeating. Persists across restarts."""
    used = _load_used()
    available = [i for i in range(len(STORIES)) if i not in used]
    if not available:
        used = []
        available = list(range(len(STORIES)))
    idx = random.choice(available)
    used.append(idx)
    _save_used(used)
    return STORIES[idx]

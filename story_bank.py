"""
story_bank.py — Proven viral hooks + full stories.
Used as fallback when Reddit produces nothing with score >= 7.
Rotates through all 15 so every video is different.
"""

import random

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
]

_used: list[int] = []


def get_story() -> dict:
    """Return the next story, cycling through all 15 before repeating."""
    global _used
    available = [i for i in range(len(STORIES)) if i not in _used]
    if not available:
        _used = []
        available = list(range(len(STORIES)))
    idx = random.choice(available)
    _used.append(idx)
    return STORIES[idx]

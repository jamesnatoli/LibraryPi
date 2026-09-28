#!/usr/bin/python3
# Use the tmsbsimple API to find a path to different movies
# James Natoli, 2023

# This incredible api
import tmdbsimple as tmdb
tmdb.API_KEY = '5587ae2ba7f97445ae7853fc879bc044'

from pathlib import Path
import subprocess
import shlex
import re
import os
from tqdm import tqdm

def printStarring( movie):
    """Pretty print cast of a movie"""
    print('\nStarring...')
    actorlist = movie.credits()['cast']
    i = 0
    for actor in actorlist:
        if i > 3: break
        print(f'\t{actor['name']} as {actor['character']}')
        i = i + 1

def runCommandWithProgress( cmd, debug=1):
    if (debug): print (f'>> {cmd}')
    run_handbrake_with_progress(shlex.split(cmd))
        
def runCommand( cmd, debug=1):
    if (debug): print (f'>> {cmd}')
    return subprocess.run( shlex.split(cmd), capture_output=True, text=True, encoding='utf-8')

def checkMountPoint(debug=1):
    # Check what's there
    matched = []
    check_results = runCommand( 'df -h', debug)
    for line in check_results.stdout.splitlines():
        if debug: print(line)
        if (re.search('/dev/sr0.*', line)):
            matched = line.split()

    return matched

def selectMovie( query, confirmMovie=True):
    """Helper function to select a movie"""
    search = tmdb.Search()
    search.movie(query=query)
    for mv in search.results:
        print( f'Title: {mv["title"]}')
        print( f'Release Year:  {mv["release_date"][:4]}')
        print( f'\nOverview: {mv["overview"]}')

        # add starring here... top 3 prolly good enough?
        movie = tmdb.Movies( mv['id'])
        movie.info()
        printStarring(movie)

        print('\n')
        # TBD if I want to keep this... sometimes movies have been remade
        # if query.lower() == mv['title'].lower():
        #     print(f'Exact match found... proceeding automatically with {mv["title"]} ({mv["release_date"][:4]})')
        #     return movie
        # elif not confirmMovie or (input("Is this the movie you want? (yes/no)\n").lower() == "yes"):
        #     print('\n')
        #     return movie
        if (input("Is this the movie you want? (yes/no)\n").lower() == "yes"):
            print('\n')
            return movie

    print(f'Couldn\'t find the movie that you wanted from query: {query}')
    print("Exiting...")
    return None

def run_handbrake_with_progress(cmd_args: list):
    """
    Runs a HandBrakeCLI command list and parses progress in real-time 
    to drive a terminal progress bar.
    """
    # Force HandBrake to output standard stream logs line-by-line
    # We combine stderr into stdout because HandBrake sends progress blocks to stderr
    process = subprocess.Popen(
        cmd_args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    # Initialize tqdm progress bar set to 100%
    pbar = tqdm(total=100, desc="Encoding DVD", unit="%", bar_format="{l_bar}{bar}| {n:.2f}/{total_fmt} % [{elapsed}<{remaining}]")
    
    # Regex pattern to capture the percentage number
    # Matches: "Encoding: task 1 of 1, 45.21 %"
    progress_pattern = re.compile(r"Encoding:.*,\s+([\d.]+)\s+%")
    
    last_pct = 0.0

    # Read the output stream as HandBrake generates it
    for line in iter(process.stdout.readline, ""):
        match = progress_pattern.search(line)
        if match:
            current_pct = float(match.group(1))
            
            # Calculate how much to advance the progress bar
            increment = current_pct - last_pct
            if increment > 0:
                pbar.update(increment)
                last_pct = current_pct

    # Clean up and ensure process finishes
    process.stdout.close()
    return_code = process.wait()
    pbar.close()

    if return_code == 0:
        print("\nEncoding complete successfully!")
    else:
        print(f"\nHandBrake failed with exit code: {return_code}")

    return return_code

def find_handbrake_title(log_output):
    """
    Parses HandBrake scan text to find the best title index for the main feature.
    
    Returns:
        int: The optimal title index number (e.g., 11) if a valid feature is found.
        None: If no valid title meets the criteria (> 1 hour, valid chapters).
    """
    # 1. Verify that HandBrake reported finding valid titles
    title_count_match = re.search(r"libhb:\s+scan\s+thread\s+found\s+(\d+)\s+valid\s+title", log_output)
    if not title_count_match or int(title_count_match.group(1)) == 0:
        print('Failed to find titles, scan failed')
        return None

    # 2. Isolate the final summary block at the bottom of the log
    summary_block_match = re.search(r"libhb: scan thread found \d+ valid title\(s\)(.*)", log_output, re.DOTALL)
    if not summary_block_match:
        print('Failed to locate final summary block, scan failed')
        return None
    summary_text = summary_block_match.group(1)

    # 3. Find and extract ALL individual title blocks and track the best candidate
    title_blocks = re.findall(r"(\+\s+title\s+\d+:.*?)(?=\+\s+title\s+\d+:|\Z)", summary_text, re.DOTALL)
    if not title_blocks:
        print('Failed to extract individual title structures, scan failed')
        return None

    best_title_index = None
    longest_duration = 0

    # 4. Iterate through every title block to find the longest valid candidate
    for block in title_blocks:
        # Extract the title index number from the header line (e.g., "+ title 11:")
        index_match = re.search(r"\+\s+title\s+(\d+):", block)
        if not index_match:
            continue
        current_index = int(index_match.group(1))

        # Check if this specific title block has a chapters subsection
        if "+ chapters:" not in block:
            continue

        # Extract all chapter durations inside this block
        chapter_pattern = r"\+\s+(\d+):\s+duration\s+(\d{2}:\d{2}:\d{2})"
        chapters = re.findall(chapter_pattern, block)
        if not chapters:
            continue

        # Validate chapter durations and accumulate total time
        has_invalid_chapter = False
        current_title_duration = 0
        
        for chap_num, duration in chapters:
            if duration == "00:00:00":
                has_invalid_chapter = True
                break
            
            h, m, s = map(int, duration.split(':'))
            current_title_duration += (h * 3600) + (m * 60) + s

        # Skip this title if it contains corrupt/zero-length chapters
        if has_invalid_chapter:
            continue

        # 5. Track the absolute longest valid title that clears the 1-hour marker
        if current_title_duration >= 3600 and current_title_duration > longest_duration:
            longest_duration = current_title_duration
            best_title_index = current_index

    # Final Evaluation
    if best_title_index is not None:
        print(f"Optimal title found: Index {best_title_index} ({longest_duration} seconds)")
        return best_title_index

    print('No individual title met the main feature requirements (>1hr, valid chapters).')
    return None

def mergeMovies( newMovieDir, newMovieFilename, movieFile):
    mergedMovieFilename = f'{newMovieDir}/{newMovieFilename[:-4]}_MERGED.mkv'

    # Merge the new file into the existing one
    merge_result = runCommand( f'mkvmerge --output "{mergedMovieFilename}" "{newMovieDir}/{newMovieFilename}" + {movieFile}')

    # Extract the messy chapters
    initial_chapters = f'{newMovieDir}/messy_movie_chapters.xml'
    extract_result = runCommand( f'mkvextract "{mergedMovieFilename}" chapters --simple "{initial_chapters}"')
    
    # Fix the chapters
    chapter_count = 0
    fixed_chapters = f'{newMovieDir}/fixed_movie_chapters.xml'
    with open( initial_chapters, "r") as infile, open(fixed_chapters, "w") as outfile:
        for line in infile:
            line = line.strip()
            # Find lines containing timestamps (e.g., CHAPTER01=00:00:00.083)
            if line.startswith("CHAPTER") and "=" in line and not "NAME" in line:
                chapter_count += 1
                timestamp = line.split("=")[1]
                
                # Write cleanly padded keys and generic sequential names
                outfile.write(f"CHAPTER{chapter_count:02d}={timestamp}\n")
                outfile.write(f"CHAPTER{chapter_count:02d}NAME=Chapter {chapter_count}\n")
    
    # load the fixed chapters back in
    loadchapters_result = runCommand( f'mkvpropedit "{mergedMovieFilename}" --chapters "{fixed_chapters}"')

    # clean up
    print('Cleaning up merged files...')
    rm_oldchapters_result = runCommand( f'rm "{initial_chapters}"')
    rm_newchapters_result = runCommand( f'rm "{fixed_chapters}"')

    rm_newfile_result = runCommand( f'rm "{movieFile}"')
    rm_oldfile_result = runCommand( f'rm "{newMovieDir}/{newMovieFilename}"')
    mv_mergedfile_result = runCommand( f'mv "{mergedMovieFilename}" "{newMovieDir}/{newMovieFilename}"')

def main():
    debug = 0
    sourceDirectory = "/media/Seagate/temp/"
    targetDirectory = "/media/Seagate/Movies/"

    # Check what's there
    matched = checkMountPoint(debug)
    if len(matched) == 0:
        print('No media mounted at /dev/sr0... attempting to mount')
        # Mount the drive
        runCommand( 'udisksctl mount -b /dev/sr0')
        matched = checkMountPoint(debug)
        
        # Check if mount successfull
        if len(matched) == 0:
            print('No media able to be mounted at /dev/sr0... exiting')
            exit(1)

    moviePath = matched[-1]
    movieFile = f"{sourceDirectory}/{moviePath.split('/')[-1]}.mkv"
    movieToProcess = moviePath.split('/')[-1].replace('_', ' ')

    if not os.path.isfile(movieFile):
        # check for VIDEO_TS
        if not os.path.isdir(f'{moviePath}/VIDEO_TS'):
            print(f'No valid VIDEO_TS directory in {moviePath}, exiting')
            exit(1)
    
        print(f'Processing: {moviePath}\n')

        # Handbrake Scan
        handbrakeScan_result = runCommand( f'HandBrakeCLI -i {moviePath}/VIDEO_TS/ -t 0')
        # if not verify_handbrake_scan(handbrakeScan_result.stderr):
        handbrake_title = find_handbrake_title(handbrakeScan_result.stderr)
        if handbrake_title is None:
            print('Scan was unsuccessful... exiting')
            exit(1)

        print(f'Scan was successful! Now processing title {handbrake_title} with Handbrake')
        runCommandWithProgress( f'HandBrakeCLI -i {moviePath}/VIDEO_TS/ -o {movieFile} -t {handbrake_title}')
    else: # TODO: Fix this... should be able to start mid-workflow
        print(f'Movie file {movieFile} already exists, organizing this first')
        
    movie = selectMovie(movieToProcess)
    while movie is None:
        movie = selectMovie(input(f'Please input another search:\n'))

    if movieFile == '':
        print(f'Failed to find movie file (.mkv) for {movieFile}')
        exit(1)

    print(f"Creating directory for '{movie.title}' from file {movieFile}")

    newMovieDir = f'{targetDirectory}{movie.title} ({movie.release_date[:4]}) {{tmdb-{movie.id}}}'
    newMovieFilename = f'{movie.title} ({movie.release_date[:4]}) {{tmdb-{movie.id}}}{Path(movieFile).suffix}'

    # 2-Part Movie
    if os.path.isdir(newMovieDir) and os.path.isfile(f'{newMovieDir}/{newMovieFilename}'):
        print(f'Directory already exists... attempting to merge {movieFile} and {newMovieDir}/{newMovieFilename}')
        mergeMovies( newMovieDir, newMovieFilename, movieFile)
    else: # Regular Movie
        runCommand(f'mkdir "{newMovieDir}"')
        runCommand(f'mv "{movieFile}" "{newMovieDir}/{newMovieFilename}"')
        # cmd = ['mkdir', newMovieDir]
        # if debug: print( cmd)
        # proc = subprocess.run( cmd)
        # 
        # cmd = ['mv', movieFile, f'{newMovieDir}/{newMovieFilename}']
        # if debug: print(cmd)
        # proc = subprocess.run( cmd)
        
    print("\nDone :)")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt as e:
        print( "ok, bye!")
